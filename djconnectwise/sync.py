import datetime
import logging
import math
import os
from copy import deepcopy
from decimal import Decimal
from retrying import retry

from botocore.exceptions import NoCredentialsError
from dateutil.parser import parse
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.storage import default_storage
from django.db import transaction, IntegrityError, DatabaseError
from django.db.models import Q
from django.utils import timezone
from django.utils.text import normalize_newlines
from djconnectwise import api
from djconnectwise import models
from djconnectwise.utils import DjconnectwiseSettings, \
    parse_sla_status
from djconnectwise.api import ConnectWiseAPIError, \
    ConnectWiseSecurityPermissionsException
from djconnectwise.utils import get_hash, get_filename_extension, \
    generate_thumbnail, generate_filename, remove_thumbnail

DEFAULT_AVATAR_EXTENSION = 'jpg'

CREATED = 1
UPDATED = 2
SKIPPED = 3
FILE_UMASK = 0o022

MAX_POSITIVE_SMALL_INT = 32767
# See https://docs.djangoproject.com/en/dev/ref/models/fields
# /#positivesmallintegerfield

logger = logging.getLogger(__name__)


class InvalidObjectException(Exception):
    """
    If for any reason an object can't be created (for example, it references
    an unknown foreign object, or is missing a required field), raise this
    so that the synchronizer can catch it and continue with other records.
    """
    pass


def log_sync_job(f):
    def wrapper(*args, **kwargs):
        sync_instance = args[0]
        created_count = updated_count = deleted_count = skipped_count = 0
        sync_job = models.SyncJob()
        sync_job.start_time = timezone.now()
        sync_job.entity_name = sync_instance.model_class.__bases__[0].__name__
        sync_job.synchronizer_class = \
            sync_instance.__class__.__name__

        if sync_instance.full:
            sync_job.sync_type = 'full'
        else:
            sync_job.sync_type = 'partial'

        sync_job.save()

        try:
            created_count, updated_count, skipped_count, deleted_count = \
                f(*args, **kwargs)
            sync_job.success = True
        except Exception as e:
            sync_job.message = str(e.args[0])
            sync_job.success = False
            raise
        finally:
            sync_job.end_time = timezone.now()
            sync_job.added = created_count
            sync_job.updated = updated_count
            sync_job.skipped = skipped_count
            sync_job.deleted = deleted_count
            sync_job.save()

        return created_count, updated_count, skipped_count, deleted_count
    return wrapper


class SyncResults:
    """Track results of a sync job."""
    def __init__(self):
        self.created_count = 0
        self.updated_count = 0
        self.skipped_count = 0
        self.deleted_count = 0
        self.synced_ids = set()


class Synchronizer:
    lookup_key = 'id'
    bulk_prune = True

    def __init__(self, full=False, *args, **kwargs):
        self.api_conditions = []
        self.partial_sync_support = True
        self.client = self.client_class()
        request_settings = DjconnectwiseSettings().get_settings()
        self.batch_size = request_settings['batch_size']
        self.full = full

        self.pre_delete_callback = kwargs.pop('pre_delete_callback', None)
        self.pre_delete_args = kwargs.pop('pre_delete_args', None)
        self.post_delete_callback = kwargs.pop('post_delete_callback', None)

    def set_relations(self, instance, json_data):
        for json_field, value in self.related_meta.items():
            model_class, field_name = value
            self._assign_relation(
                instance,
                json_data,
                json_field,
                model_class,
                field_name
            )

    @staticmethod
    def _assign_null_relation(instance, model_field):
        """
        Set the FK to null, but handle issues like the FK being non-null.

        This can happen because ConnectWise gives us records that point to
        non-existent records- such as activities whose assignTo fields point
        to deleted members.
        """
        try:
            setattr(instance, model_field, None)
        except ValueError:
            # The model_field may have been non-null.
            raise InvalidObjectException(
                "Unable to set field {} on {} to null, as it's required.".
                format(model_field, instance)
            )

    def _assign_relation(self, instance, json_data,
                         json_field, model_class, model_field):
        """
        Look up the given foreign relation, and set it to the given
        field on the instance.
        """
        relation_json = json_data.get(json_field)
        if relation_json is None:
            self._assign_null_relation(instance, model_field)
            return

        uid = relation_json['id']

        try:
            related_instance = model_class.objects.get(pk=uid)
            setattr(instance, model_field, related_instance)
        except model_class.DoesNotExist:
            logger.warning(
                'Failed to find {} {} for {} {}.'.format(
                    json_field,
                    uid,
                    type(instance),
                    instance.id
                )
            )
            self._assign_null_relation(instance, model_field)

    def _instance_ids(self, filter_params=None):
        if not filter_params:
            ids = self.model_class.objects.all().order_by(self.lookup_key)\
                .values_list(self.lookup_key, flat=True)
        else:
            ids = self.model_class.objects.filter(filter_params)\
                .order_by(self.lookup_key)\
                .values_list(self.lookup_key, flat=True)
        return set(ids)

    def get(self, results, conditions=None):
        return self.fetch_records(results, conditions)

    def fetch_records(self, results, conditions=None):
        """
        For all pages of results, save each page of results to the DB.

        If conditions is supplied in the call, then use only those conditions
        while fetching pages of records. If it's omitted, then use
        self.api_conditions.
        """
        page = 1
        while True:
            logger.info(
                'Fetching {} records, batch {}'.format(
                    self.model_class.__bases__[0].__name__, page)
            )
            page_conditions = conditions or self.api_conditions
            page_records = self.get_page(
                page=page, page_size=self.batch_size,
                conditions=page_conditions,
            )
            self.persist_page(page_records, results)
            page += 1
            if len(page_records) < self.batch_size:
                # This page wasn't full, so there's no more records after
                # this page.
                break
        return results

    def persist_page(self, records, results):
        """Persist one page of records to DB."""
        for record in records:
            try:
                with transaction.atomic():
                    instance, result = self.update_or_create_instance(record)
                if result == CREATED:
                    results.created_count += 1
                elif result == UPDATED:
                    results.updated_count += 1
                else:
                    results.skipped_count += 1
            except (IntegrityError, InvalidObjectException) as e:
                logger.warning('{}'.format(e))

            results.synced_ids.add(record['id'])

        return results

    def get_page(self, *args, **kwargs):
        raise NotImplementedError

    def get_single(self, *args, **kwargs):
        raise NotImplementedError

    def _assign_field_data(self, instance, api_instance):
        raise NotImplementedError

    def fetch_sync_by_id(self, instance_id, sync_config={}):
        api_instance = self.get_single(instance_id)
        instance, created = self.update_or_create_instance(api_instance)
        return instance

    def fetch_delete_by_id(self, instance_id, pre_delete_callback=None,
                           pre_delete_args=None,
                           post_delete_callback=None):
        try:
            self.get_single(instance_id)
            logger.warning(
                'ConnectWise API returned {} {} even though it was expected '
                'to be deleted.'.format(
                    self.model_class.__bases__[0].__name__, instance_id)
            )

        except api.ConnectWiseRecordNotFoundError:
            # This is what we expect to happen. Since it's gone in CW, we
            # are safe to delete it from here.
            pre_delete_result = None
            try:
                if pre_delete_callback:
                    pre_delete_result = pre_delete_callback(*pre_delete_args)
                self.model_class.objects.filter(pk=instance_id).delete()
            finally:
                if post_delete_callback:
                    post_delete_callback(pre_delete_result)
            logger.info(
                'Deleted {} {} (if it existed).'.format(
                    self.model_class.__bases__[0].__name__,
                    instance_id
                )
            )

    def _is_instance_changed(self, instance):
        return instance.tracker.changed()

    def update_or_create_instance(self, api_instance):
        """
        Creates and returns an instance if it does not already exist.
        """
        result = None
        api_instance = self.remove_null_characters(api_instance)
        try:
            instance_pk = api_instance[self.lookup_key]
            instance = self.model_class.objects.get(pk=instance_pk)
        except self.model_class.DoesNotExist:
            instance = self.model_class()
            result = CREATED

        try:
            self._assign_field_data(instance, api_instance)

            # This will return the created instance, the updated instance, or
            # if the instance is skipped an unsaved copy of the instance.
            if result == CREATED:
                if self.model_class is models.TicketTracker:
                    instance.save(force_insert=True)
                else:
                    instance.save()
            elif self._is_instance_changed(instance):
                instance.save()
                result = UPDATED
            else:
                result = SKIPPED
        except AttributeError as e:
            msg = "AttributeError while attempting to sync object {}." \
                  " Error: {}".format(self.model_class, e)
            logger.error(msg)
            raise InvalidObjectException(msg)
        except IntegrityError as e:
            # This can happen when multiple threads are creating the
            # same ticket at once. See issue description for #991
            # for the full details.
            msg = "IntegrityError while attempting to create {}." \
                  " Error: {}".format(self.model_class, e)
            logger.error(msg)
            raise InvalidObjectException(msg)

        if result == CREATED:
            result_log = 'Created'
        elif result == UPDATED:
            result_log = 'Updated'
        else:
            result_log = 'Skipped'

        logger.info('{}: {} {}'.format(
            result_log,
            self.model_class.__bases__[0].__name__,
            instance
        ))

        return instance, result

    def prune_stale_records(self, initial_ids, synced_ids):
        """
        Delete records that existed when sync started but were
        not seen as we iterated through all records from REST API.
        """
        stale_ids = initial_ids - synced_ids
        deleted_count = 0
        if stale_ids:
            delete_qset = self.get_delete_qset(stale_ids)
            deleted_count = delete_qset.count()

            pre_delete_result = None
            if self.pre_delete_callback:
                pre_delete_result = self.pre_delete_callback(
                    *self.pre_delete_args
                )
            logger.info(
                'Removing {} stale records for model: {}'.format(
                    len(stale_ids), self.model_class.__bases__[0].__name__,
                )
            )
            if self.bulk_prune:
                delete_qset.delete()
            else:
                for instance in delete_qset:
                    try:
                        instance.delete()
                    except IntegrityError as e:
                        logger.exception(
                            'IntegrityError while attempting to '
                            'delete {} records. Error: {}'.format(
                                self.model_class.__bases__[0].__name__,
                                e.__cause__
                            )
                        )

            if self.post_delete_callback:
                self.post_delete_callback(pre_delete_result)

        return deleted_count

    def get_delete_qset(self, stale_ids):
        return self.model_class.objects.filter(pk__in=stale_ids)

    def get_sync_job_qset(self):
        return models.SyncJob.objects.filter(
            entity_name=self.model_class.__bases__[0].__name__
        )

    @log_sync_job
    def sync(self):
        sync_job_qset = self.get_sync_job_qset()

        # Since the job is created before it begins, make sure to exclude
        # itself, and at least one other sync job exists.
        if sync_job_qset.count() > 1 and not self.full and \
                self.partial_sync_support:
            send_naive_datetimes = (
                DjconnectwiseSettings().get_settings())['send_naive_datetimes']
            if send_naive_datetimes:
                last_sync_job = sync_job_qset.exclude(
                    id=sync_job_qset.last().id)
                last_sync_job_time = last_sync_job.last().start_time.strftime(
                    '%Y-%m-%dT%H:%M:%S.%f')
            else:
                last_sync_job_time = sync_job_qset.exclude(
                    id=sync_job_qset.last().id).last().start_time.isoformat()
            self.api_conditions.append(
                "lastUpdated>[{0}]".format(last_sync_job_time)
            )
        results = SyncResults()

        # Set of IDs of all records prior to sync,
        # to find stale records for deletion.
        initial_ids = self._instance_ids() if self.full else []

        results = self.get(results, )

        if self.full:
            results.deleted_count = self.prune_stale_records(
                initial_ids, results.synced_ids
            )

        return results.created_count, results.updated_count, \
            results.skipped_count, results.deleted_count

    def callback_sync(self, filter_params):

        results = SyncResults()

        # Set of IDs of all records related to the parent object
        # to sync, to find stale records for deletion, need to be careful
        # to get the correct filter on the objects you want, or you will
        # be deleting records you didn't intend to, and they wont be restored
        # until their next scheduled sync
        initial_ids = self._instance_ids(filter_params=filter_params)
        results = self.get(results, )

        # This should always be a full sync (unless something changes in
        # the future and it doesn't need to delete anything)
        results.deleted_count = self.prune_stale_records(
            initial_ids, results.synced_ids
        )

        return results.created_count, results.updated_count, \
            results.skipped_count, results.deleted_count

    def sync_children(self, *args):
        for synchronizer, filter_params in args:
            created_count, updated_count, skipped_count, deleted_count \
                = synchronizer.callback_sync(filter_params)
            msg = '{} Child Sync - Created: {},'\
                ' Updated: {}, Skipped: {}, Deleted: {}'.format(
                    synchronizer.model_class.__bases__[0].__name__,
                    created_count,
                    updated_count,
                    skipped_count,
                    deleted_count
                )
            logger.info(msg)

    def remove_null_characters(self, json_data):
        for value in json_data:
            if isinstance(json_data.get(value), str):
                json_data[value] = json_data[value].replace('\x00', '')

        return json_data

    def _translate_fields_to_api_format(self, model_field_data):
        """
        Converts the model field names to the API field names.
        """
        api_fields = {}
        for key, value in model_field_data.items():
            api_fields[self.API_FIELD_NAMES[key]] = value

        return api_fields


class BatchConditionMixin:
    """
    Yo I heard you like pages, so I put pages in your pages!

    This mixin has methods for Synchronizers that have to page their pagers.
    For example, syncing the tickets in a set of statuses- there can be
    too many statuses to fit all their IDs in one URL, given the max URL
    size of approximately 2000 characters. So we split the statuses into
    groups that get the URL close to 2000 characters, and get those results
    in pages. And then get the next set of statuses in pages, and so on.
    """
    def get_batch_condition(self, conditions):
        raise NotImplementedError

    def get(self, results, conditions=None):
        """Buffer and return all pages of results."""
        unfetched_conditions = deepcopy(self.batch_condition_list)
        while unfetched_conditions:
            # While there are still items left in the list there are still
            # batches left to be fetched.
            optimal_size = self.get_optimal_size(
                unfetched_conditions,
                self.client.request_settings['max_url_length']
            )
            batch_conditions = unfetched_conditions[:optimal_size]
            del unfetched_conditions[:optimal_size]
            batch_condition = self.get_batch_condition(batch_conditions)
            batch_conditions = deepcopy(self.api_conditions)
            batch_conditions.append(batch_condition)
            results = super().get(results, conditions=batch_conditions)
        return results

    def get_optimal_size(self, condition_list, max_url_length=2000,
                         min_url_length=None):
        if not condition_list:
            # Return none if empty list
            return None
        size = len(condition_list)

        if not min_url_length:
            min_url_length = max_url_length - 20

        if self.url_length(condition_list, size) < max_url_length:
            # If we can fit all of the statuses in the first batch, return
            return size

        max_size = size
        min_size = 1
        while True:
            url_len = self.url_length(condition_list, size)
            if url_len <= max_url_length and url_len > min_url_length:
                break
            elif url_len > max_url_length:
                max_size = size
                size = math.floor((max_size+min_size)/2)
            else:
                min_size = size
                size = math.floor((max_size+min_size)/2)
            if min_size == 1 and max_size == 1:
                # The URL cannot be made short enough. This ought never to
                # happen in production.
                break
        return size

    @staticmethod
    def url_length(condition_list, size):
        # We add the approximate amount of characters for the URL that we
        # know will be there every time (200) plus a little more to ensure we
        # don't undercut it (300), and add (3 * size), because for the number
        # of conditions, there will be the same number of commas separating
        # them but commas are urlencoded to %2C which is 3 characters.
        return (sum(len(str(i)) for i in condition_list[:size])
                + 300 + (3 * size))


class CallbackSyncMixin:
    """
    Run a partial sync on callbacks for related synchronizers. If a ticket
    has many notes or time entries they could all be fetched
    when a callback runs. This could mean a lot of time and resources spent
    syncing old notes or time entries.
    The exception to this rule is if a ticket is created by a callback. In this
    case, the related note and time entry sync will be full not partial.
    This is because in most cases, a partial note sync that runs when a
    ticket is created will miss most or all notes and time entries for
    a ticket.
    We will continue to return deleted_count even though it will always
    be zero in this case.
    """
    sync_all = False

    def callback_sync(self, filter_params):
        sync_job_qset = self.get_sync_job_qset()

        if sync_job_qset.exists() and not self.sync_all:
            send_naive_datetimes = (
                DjconnectwiseSettings().get_settings())['send_naive_datetimes']
            last_sync_job = sync_job_qset.last()
            if send_naive_datetimes:
                last_sync_job_time = last_sync_job.start_time.strftime(
                    '%Y-%m-%dT%H:%M:%S.%f')
            else:
                last_sync_job_time = last_sync_job.start_time.isoformat()
            self.api_conditions.append(
                "lastUpdated>[{0}]".format(last_sync_job_time)
            )

        results = SyncResults()
        results = self.get(results, )

        return results.created_count, results.updated_count, \
            results.skipped_count, results.deleted_count


class ChildFetchRecordsMixin:
    parent_model_class = None
    sync_single_id = None

    def get_total_pages(self, results, conditions=None, object_id=None):
        """
        For all pages of results, save each page of results to the DB.

        If conditions is supplied in the call, then use only those conditions
        while fetching pages of records. If it's omitted, then use
        self.api_conditions.
        """
        page_conditions = conditions or self.api_conditions
        page = 1
        while True:
            logger.info(
                'Fetching {} records: {} id {}, page {}'.format(
                    self.model_class.__bases__[0].__name__,
                    self.parent_model_class.__name__,
                    object_id, page)
            )
            page_records = self.get_page(
                page=page, page_size=self.batch_size,
                conditions=page_conditions,
                object_id=object_id,
            )
            self.persist_page(page_records, results)
            page += 1

            if len(page_records) < self.batch_size:
                # This page wasn't full, so there's no more records after
                # this page.
                break
        return results

    def fetch_records(self, results, conditions=None):

        for object_id in self.parent_object_ids:
            try:
                self.get_total_pages(
                    results,
                    conditions=conditions,
                    object_id=object_id,
                )
            except ConnectWiseSecurityPermissionsException:
                # Pass boards TopLeft may not have access to so the
                #  whole sync doesn't fail
                continue

        return results

    def get_page(self, *args, **kwargs):
        object_id = kwargs.get('object_id')
        return self.client_call(object_id, *args, **kwargs)

    @property
    def parent_object_ids(self):
        if self.sync_single_id:
            # On callbacks we will only want to fetch records for a single ID
            # not all model records in the database.
            object_ids = [self.sync_single_id]
        else:
            object_ids = self.parent_model_class.objects.all().order_by(
                self.lookup_key).values_list(self.lookup_key, flat=True)

        return object_ids


class CreateRecordMixin:

    def create(self, fields, **kwargs):
        """
        Send POST request to ConnectWise to create a record.
        """
        client = self.client_class(
            api_public_key=kwargs.get('api_public_key'),
            api_private_key=kwargs.get('api_private_key')
        )
        # Convert the fields to the format that the API expects
        api_fields = self._translate_fields_to_api_format(fields)

        new_record = self.create_record(client, api_fields)

        return self.update_or_create_instance(new_record)

    def create_record(self, client, api_fields):
        raise NotImplementedError


class UpdateRecordMixin:

    def update(self, record, changed_fields, **kwargs):
        """
        Send PATCH request to ConnectWise to update a record.
        """
        client = self.client_class(
            api_public_key=kwargs.get('api_public_key'),
            api_private_key=kwargs.get('api_private_key')
        )

        # Convert the fields to the format that the API expects
        api_fields = self._translate_fields_to_api_format(changed_fields)

        updated_record = self.update_record(client, record, api_fields)

        return self.update_or_create_instance(updated_record)

    def update_record(self, client, record, api_fields):
        raise NotImplementedError


class ServiceNoteSynchronizer(ChildFetchRecordsMixin, CallbackSyncMixin,
                              Synchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.ServiceNoteTracker
    parent_model_class = models.Ticket

    related_meta = {
        'member': (models.Member, 'member')
    }

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')

        text = json_data.get('text')
        if text:
            instance.text = normalize_newlines(text)
        instance.detail_description_flag = json_data.get(
            'detailDescriptionFlag')
        instance.internal_analysis_flag = json_data.get(
            'internalAnalysisFlag')
        instance.resolution_flag = json_data.get(
            'resolutionFlag')
        instance.created_by = json_data.get('createdBy')
        instance.internal_flag = json_data.get('internalFlag')
        instance.external_flag = json_data.get('externalFlag')

        date_created = json_data.get('dateCreated')
        if date_created:
            instance.date_created = parse(date_created)

        ticket_class = models.Ticket

        try:
            ticket_id = json_data.get('ticketId')
            related_ticket = ticket_class.objects.get(pk=ticket_id)
            setattr(instance, 'ticket', related_ticket)
        except AttributeError:
            raise InvalidObjectException(
                'Service note {} has no ticketId key to find its target'
                '- skipping.'.format(instance.id)
            )
        except ObjectDoesNotExist as e:
            raise InvalidObjectException(
                'Service note {} has a ticketId that does not exist.'
                ' ObjectDoesNotExist Exception: {}'.format(instance.id, e)
            )

        self.set_relations(instance, json_data)

    def client_call(self, ticket_id, *args, **kwargs):
        return self.client.get_notes(ticket_id, *args, **kwargs)

    def create_new_note(self, target, **kwargs):
        """
        Send POST request to ConnectWise to create a new note and then
        create it in the local database from the response
        """

        target_data = {}

        if isinstance(target, models.Ticket):
            target_data['id'] = target.id
            target_data['type'] = target.record_type
        else:
            raise ValueError(
                "Invalid target type for note creation: {}.".format(
                    str(target.__class__))
            )
        service_client = api.ServiceAPIClient(
            api_public_key=kwargs.get('api_public_key'),
            api_private_key=kwargs.get('api_private_key')
        )
        instance = service_client.post_note(target_data, **kwargs)

        return self.update_or_create_instance(instance)


###################################################################
# Dummy Synchronizers                                             #
###################################################################


class DummySynchronizer:
    # Use FIELDS to list fields we submit to create or update a record, used
    # as a kind of validation method and way to link the snake_case field
    # names to their camelCase api names
    FIELDS = {}

    def __init__(self, *args, **kwargs):
        self.api_conditions = []
        self.client = self.client_class(
            api_public_key=kwargs.get('api_public_key'),
            api_private_key=kwargs.get('api_private_key')
        )
        request_settings = DjconnectwiseSettings().get_settings()
        self.batch_size = request_settings['batch_size']

    def get(self, parent=None, conditions=None):
        """
        If conditions is supplied in the call, then use only those conditions
        while fetching pages of records. If it's omitted, then use
        self.api_conditions.
        """
        page = 1
        records = []

        while True:
            logger.info(
                'Fetching {} records, batch {}'.format(
                    self.RECORD_NAME, page)
            )
            page_conditions = conditions or self.api_conditions
            page_records = self.get_page(
                parent=parent, page=page, page_size=self.batch_size,
                conditions=page_conditions,
            )

            records += page_records
            page += 1
            if len(page_records) < self.batch_size:
                # This page wasn't full, so there's no more records after
                # this page.
                break

        inverted = {v: k for k, v in self.FIELDS.items()}
        formatted_records = []

        # Convert the results from camelCase back to snake_case
        for record in records:
            converted = {}
            for k, v in record.items():
                if inverted.get(k, None):
                    converted[inverted[k]] = v
            formatted_records.append(converted)

        return formatted_records

    def update(self, parent=None, **kwargs):
        raise NotImplementedError

    def create(self, parent=None, **kwargs):
        raise NotImplementedError

    def delete(self, parent=None, **kwargs):
        raise NotImplementedError

    def get_page(self, parent=None, **kwargs):
        raise NotImplementedError

    def _format_record(self, **kwargs):
        record = {}
        for key, value in kwargs.items():
            # Only consider fields of the record, discard anything else
            if key in self.FIELDS.keys():
                record[self.FIELDS[key]] = value

        return record


class TicketTaskSynchronizer:
    FIELDS = {
        'id': 'id',
        'closed_flag': 'closedFlag',
        'priority': 'priority',
        'task': 'notes',
        'schedule': 'schedule'
    }
    RECORD_TYPE = models.Ticket.SERVICE_TICKET
    RECORD_NAME = "TicketTask"

    def update(self, parent=None, **kwargs):
        record = self._format_record(**kwargs)

        return self.client.update_ticket_task(
            kwargs.get('id'), parent, **record)

    def create(self, parent=None, **kwargs):
        record = self._format_record(**kwargs)

        return self.client.create_ticket_task(parent, **record)

    def delete(self, parent=None, **kwargs):
        return self.client.delete_ticket_task(parent, **kwargs)

    def get_page(self, parent=None, **kwargs):
        return self.client.get_ticket_tasks(parent, **kwargs)

    def sync(self):
        ticket_qs = self._get_queryset()

        for ticket in ticket_qs:
            self.sync_items(ticket)

    def sync_items(self, instance):
        tasks = self.get(parent=instance.id)

        # When the PSA goes crazy, stay within the bounds of a small int.
        instance.tasks_total = min(
            MAX_POSITIVE_SMALL_INT, len(tasks)
        )
        instance.tasks_completed = min(
            MAX_POSITIVE_SMALL_INT, sum(task['closed_flag'] for task in tasks)
        )

        try:
            instance.save(update_fields=["tasks_total", "tasks_completed"])
        except DatabaseError as e:
            # This can happen if the ticket was deleted in the background.
            logger.warning(
                'DatabaseError while processing tasks on ticket {}: '
                '{}'.format(instance, e)
            )


class ServiceTicketTaskSynchronizer(TicketTaskSynchronizer, DummySynchronizer):
    client_class = api.ServiceAPIClient

    def _get_queryset(self):
        return models.Ticket.objects.filter(
            record_type=self.RECORD_TYPE).order_by('id')


class ProjectTicketTaskSynchronizer(TicketTaskSynchronizer, DummySynchronizer):
    client_class = api.ProjectAPIClient

    def _get_queryset(self):
        return models.Ticket.objects.exclude(
            record_type=self.RECORD_TYPE).order_by('id')


class AttachmentSynchronizer:
    client_class = api.SystemAPIClient

    def __init__(self, *args, **kwargs):
        self.api_conditions = []
        self.client = self.client_class()
        request_settings = DjconnectwiseSettings().get_settings()
        self.batch_size = request_settings['batch_size']

    def get_page(self, *args, **kwargs):
        object_id = kwargs.pop('object_id')
        return self.client.get_attachments(object_id, *args, **kwargs)

    def get_count(self, object_id):
        return self.client.get_attachment_count(object_id)

    def download_attachment(self, attachment_id, path):
        filename, attachment = self.client.get_attachment(attachment_id)

        filename = f'{attachment_id}-{filename}'
        file_path = os.path.join(path, f'{filename}')

        logger.debug(f'Writing attachment {filename} to {path}')

        previous_umask = os.umask(FILE_UMASK)

        with open(file_path, 'wb') as f:
            f.write(attachment.content)

        os.umask(previous_umask)

        return filename


class OpportunityNoteSynchronizer(ChildFetchRecordsMixin, Synchronizer):
    client_class = api.SalesAPIClient
    model_class = models.OpportunityNoteTracker
    parent_model_class = models.Opportunity

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.text = json_data.get('text')

        opp_class = models.Opportunity

        date_created = json_data.get('_info').get('lastUpdated')

        if date_created:
            instance.date_created = parse(date_created)

        try:
            opportunity_id = json_data.get('opportunityId')
            related_opportunity = opp_class.objects.get(pk=opportunity_id)
            setattr(instance, 'opportunity', related_opportunity)
        except ObjectDoesNotExist as e:
            raise InvalidObjectException(
                'Opportunity note {} has a opportunityId that does not exist.'
                ' ObjectDoesNotExist Exception: {}'.format(instance.id, e)
            )

    def client_call(self, opportunity_id, *args, **kwargs):
        return self.client.get_notes(opportunity_id, *args, **kwargs)


class ConfigurationSynchronizer:
    client_class = api.ConfigurationAPIClient

    def __init__(self, *args, **kwargs):
        self.api_conditions = []
        self.client = self.client_class()
        request_settings = DjconnectwiseSettings().get_settings()
        self.batch_size = request_settings['batch_size']

    def fetch_configurations(self, company_id):
        """
        Fetch configurations from a specific company.
        """
        return self.client.get_configurations(company_id)


class ConfigurationStatusSynchronizer(Synchronizer):
    client_class = api.ConfigurationAPIClient
    model_class = models.ConfigurationStatusTracker

    related_meta = {
        'company': (models.Company, 'company'),
    }

    def _assign_field_data(self, instance, json_data):
        """
        Assigns the data from the API instance to the model instance.
        """
        instance.id = json_data.get('id')
        instance.description = json_data.get('description', '')
        instance.closed_flag = json_data.get('closedFlag', False)
        instance.default_flag = json_data.get('defaultFlag', False)

        self.set_relations(instance, json_data)
        return instance

    def get_page(self, *args, **kwargs):
        """
        Retrieves a page of configuration statuses from the API.
        """
        return self.client.get_configuration_statuses(*args, **kwargs)


class ConfigurationTypeSynchronizer(Synchronizer):
    client_class = api.ConfigurationAPIClient
    model_class = models.ConfigurationTypeTracker

    related_meta = {
        'company': (models.Company, 'company'),
    }

    def _assign_field_data(self, instance, json_data):
        """
        Assigns the data from the API instance to the model instance.
        """
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        instance.inactive_flag = json_data.get('inactiveFlag', False)
        instance.system_flag = json_data.get('systemFlag', False)

        self.set_relations(instance, json_data)
        return instance

    def get_page(self, *args, **kwargs):
        """
        Retrieves a page of configuration types from the API.
        """
        return self.client.get_configuration_types(*args, **kwargs)


class BoardSynchronizer(Synchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.ConnectWiseBoardTracker

    related_meta = {
        'workRole': (models.WorkRole, 'work_role'),
        'workType': (models.WorkType, 'work_type')
    }

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        if json_data.get('billTime') == 'NoDefault':
            instance.bill_time = None
        else:
            instance.bill_time = json_data.get('billTime')

        if 'inactiveFlag' in json_data:
            # This is the new CW way
            instance.inactive = json_data.get('inactiveFlag')
        else:
            # This is old, but keep for backwards-compatibility
            instance.inactive = json_data.get('inactive')

        instance.project_flag = json_data.get('projectFlag', False)
        instance.time_entry_discussion_flag = \
            json_data.get('timeEntryDiscussionFlag', False)
        instance.time_entry_resolution_flag = \
            json_data.get('timeEntryResolutionFlag', False)
        instance.time_entry_internal_analysis_flag = \
            json_data.get('timeEntryInternalAnalysisFlag', False)

        self.set_relations(instance, json_data)
        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_boards(*args, **kwargs)


class BoardChildSynchronizer(Synchronizer):

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        try:
            board_id = json_data['board']['id']
        except KeyError:
            # Must be 2017.5 or earlier
            board_id = json_data.get('boardId')
        instance.board = models.ConnectWiseBoard.objects.get(id=board_id)
        return instance

    def client_call(self, board_id):
        raise NotImplementedError


class BoardStatusSynchronizer(ChildFetchRecordsMixin, BoardChildSynchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.BoardStatusTracker
    parent_model_class = models.ConnectWiseBoard

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_conditions = ['inactive=False']

    def _assign_field_data(self, instance, json_data):
        instance = super(BoardStatusSynchronizer, self)._assign_field_data(
            instance, json_data)

        instance.sort_order = json_data.get('sortOrder')
        instance.display_on_board = json_data.get('displayOnBoard')
        instance.inactive = json_data.get('inactive')
        instance.closed_status = json_data.get('closedStatus')
        instance.escalation_status = json_data.get('escalationStatus')
        instance.time_entry_not_allowed = json_data.get('timeEntryNotAllowed')

        return instance

    def client_call(self, board_id, *args, **kwargs):
        return self.client.get_statuses(board_id, *args, **kwargs)


class BoardFilterMixin(ChildFetchRecordsMixin):
    parent_model_class = models.ConnectWiseBoard

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request_settings = DjconnectwiseSettings().get_settings()
        self.boards = request_settings.get('board_status_filter')

    @property
    def parent_object_ids(self):
        if self.boards:
            board_qs = self.parent_model_class.available_objects.filter(
                id__in=self.boards).order_by(self.lookup_key)
        else:
            board_qs = self.parent_model_class.available_objects.all().\
                order_by(self.lookup_key)

        return board_qs.values_list(self.lookup_key, flat=True)


class M2MAssignmentMixin:
    # indicates if many to many field info is changed or not
    m2m_changed = False

    def set_m2m_has_changed(self, instance_objects, api_objects):
        # This method works only when a model has one m2m field now.
        old_ids = [o.id for o in instance_objects]
        ids = [o.id for o in api_objects]
        self.m2m_changed = set(old_ids) != set(ids)

    def _is_instance_changed(self, instance):
        return instance.tracker.changed() or self.m2m_changed


class TeamSynchronizer(M2MAssignmentMixin, BoardFilterMixin,
                       BoardChildSynchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.TeamTracker

    def _assign_field_data(self, instance, json_data):
        instance = super(TeamSynchronizer, self)._assign_field_data(
            instance, json_data)

        members = []
        if json_data.get('members'):
            members = list(
                models.Member.objects.filter(id__in=json_data.get('members'))
            )

        instance_members = list(instance.members.all())
        self.set_m2m_has_changed(instance_members, members)
        if self.m2m_changed:
            instance.members.clear()
            instance.members.add(*members)

        return instance

    def client_call(self, board_id, *args, **kwargs):
        return self.client.get_teams(board_id, *args, **kwargs)


class CompanySynchronizer(M2MAssignmentMixin, Synchronizer):
    client_class = api.CompanyAPIClient
    model_class = models.CompanyTracker

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_conditions = [
            'deletedFlag=False',
        ]

        request_settings = DjconnectwiseSettings().get_settings()
        company_exclude_status_ids = request_settings.get(
            'company_exclude_status_ids'
        ).split(',')
        if company_exclude_status_ids:
            try:
                integer_stripped_ids = [
                    str(int(i.strip())) for i in company_exclude_status_ids
                ]
                self.api_conditions.append(
                    'status/id not in ({})'.format(
                        ','.join(integer_stripped_ids)
                    )
                )
            except ValueError:
                logger.warning(
                    'Invalid status ID(s) in company_exclude_status_ids:'
                    ' {}'.format(
                        company_exclude_status_ids
                    )
                )

    def _assign_field_data(self, company, company_json):
        """
        Assigns field data from an company_json instance
        to a local Company model instance
        """
        company.id = company_json.get('id')
        company.name = company_json.get('name')
        company.identifier = company_json.get('identifier')

        # Fields below aren't included when the company is created as a
        # side-effect of creating/updating a ticket or other type of object,
        # so use .get().
        company.phone_number = company_json.get('phoneNumber')
        company.fax_number = company_json.get('faxNumber')
        company.address_line1 = company_json.get('addressLine1')
        company.address_line2 = company_json.get('addressLine2')
        company.city = company_json.get('city')
        company.state_identifier = company_json.get('state')
        company.zip = company_json.get('zip')
        company.deleted_flag = company_json.get('deletedFlag', False)

        status_json = company_json.get('status')
        if status_json:
            try:
                status = models.CompanyStatus.objects.get(pk=status_json['id'])
                company.status = status
            except models.CompanyStatus.DoesNotExist:
                logger.warning(
                    'Failed to find CompanyStatus: {}'.format(
                        status_json['id']
                    ))

        calendar_id = company_json.get('calendarId')
        if calendar_id:
            try:
                company.calendar = models.Calendar.objects.get(id=calendar_id)
            except models.Calendar.DoesNotExist:
                logger.warning(
                    'Failed to find Calendar: {}'.format(
                        calendar_id
                    ))
        else:
            company.calendar = calendar_id

        types = []
        if company_json.get('types'):
            type_ids = [t.get('id') for t in company_json.get('types')]
            types = list(
                models.CompanyType.objects.filter(id__in=type_ids)
            )

        instance_types = list(company.company_types.all())
        self.set_m2m_has_changed(instance_types, types)
        if self.m2m_changed:
            company.company_types.clear()
            company.company_types.add(*types)

        territory = company_json.get('territory')
        if territory and territory.get('id'):
            territory_id = territory.get('id')
            try:
                company.territory = models.Territory.objects.get(
                    pk=territory_id
                )
            except models.Territory.DoesNotExist:
                logger.warning(
                    'Failed to find Territory: {}'.format(
                        territory_id
                    )
                )
        else:
            logger.warning(
                'No Territory ID received in request for Company: {}'.format(
                    company.id
                )
            )
        return company

    def get_page(self, *args, **kwargs):
        return self.client.get_companies(*args, **kwargs)

    def get_single(self, company_id):
        return self.client.by_id(company_id)

    def fetch_delete_by_id(self, company_id, pre_delete_callback=None,
                           pre_delete_args=None,
                           post_delete_callback=None):
        # Companies are deleted by setting deleted_flag = True, so
        # just treat this as a normal sync.
        pre_delete_result = None
        try:
            if pre_delete_callback:
                pre_delete_result = pre_delete_callback(*pre_delete_args)
            self.fetch_sync_by_id(company_id)
        finally:
            if post_delete_callback:
                post_delete_callback(pre_delete_result)


class CompanyStatusSynchronizer(Synchronizer):
    client_class = api.CompanyAPIClient
    model_class = models.CompanyStatusTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        instance.default_flag = json_data.get('defaultFlag')
        instance.inactive_flag = json_data.get('inactiveFlag')
        instance.notify_flag = json_data.get('notifyFlag')
        instance.dissalow_saving_flag = json_data.get('disallowSavingFlag')
        instance.notification_message = json_data.get('notificationMessage')
        instance.custom_note_flag = json_data.get('customNoteFlag')
        instance.cancel_open_tracks_flag = json_data.get(
            'cancelOpenTracksFlag'
        )

        if json_data.get('track'):
            instance.track_id = json_data.get('track').get('id')

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_company_statuses(*args, **kwargs)


class CompanyTypeSynchronizer(Synchronizer):
    client_class = api.CompanyAPIClient
    model_class = models.CompanyTypeTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        instance.vendor_flag = json_data.get('vendorFlag')
        instance.default_flag = json_data.get('defaultFlag')
        instance.service_alert_flag = json_data.get('service_alert_flag')
        instance.service_alert_message = json_data.get('service_alert_message')

    def get_page(self, *args, **kwargs):
        return self.client.get_company_types(*args, **kwargs)


class ContactTypeSynchronizer(Synchronizer):
    client_class = api.CompanyAPIClient
    model_class = models.ContactTypeTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.description = json_data.get('description')
        instance.default_flag = json_data.get('defaultFlag')
        instance.service_alert_flag = json_data.get('service_alert_flag')
        instance.service_alert_message = json_data.get('service_alert_message')

    def get_page(self, *args, **kwargs):
        return self.client.get_contact_types(*args, **kwargs)


class CompanyNoteTypesSynchronizer(Synchronizer):
    client_class = api.CompanyAPIClient
    model_class = models.CompanyNoteTypeTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        instance.identifier = json_data.get('identifier')
        instance.default_flag = json_data.get('defaultFlag')

    def get_page(self, *args, **kwargs):
        return self.client.get_company_note_types(*args, **kwargs)


class CompanyTeamSynchronizer(Synchronizer):
    client_class = api.CompanyAPIClient
    model_class = models.CompanyTeamTracker

    related_meta = {
        'company': (models.Company, 'company'),
        'teamRole': (models.CompanyTeamRole, 'team_role'),
        'location': (models.Location, 'location'),
        'contact': (models.Contact, 'contact'),
        'member': (models.Member, 'member'),

    }

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.account_manager_flag = json_data.get('accountManagerFlag')
        instance.tech_flag = json_data.get('techFlag')
        instance.sales_flag = json_data.get('salesFlag')

        self.set_relations(instance, json_data)

    def get_page(self, *args, **kwargs):
        records = []
        company_qs = models.Company.objects.all().values_list('id', flat=True)
        for company_id in company_qs:
            if company_id:
                record = self.client.get_company_team(
                    *args, **kwargs, company_id=company_id)
                if record:
                    records.extend(record)
        return records


class CompanySiteSynchronizer(Synchronizer):
    client_class = api.CompanyAPIClient
    model_class = models.CompanySiteTracker

    related_meta = {
        'company': (models.Company, 'company'),

    }

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        instance.inactive = json_data.get('inactive')

        self.set_relations(instance, json_data)

    def get_page(self, *args, **kwargs):
        records = []
        company_qs = models.Company.objects.all().values_list('id', flat=True)
        for company_id in company_qs:
            if company_id:
                record = self.client.get_company_site(
                    *args, **kwargs, company_id=company_id)
                if record:
                    records.extend(record)
        return records


class CompanyTeamRoleSynchronizer(Synchronizer):
    client_class = api.CompanyAPIClient
    model_class = models.CompanyTeamRoleTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        instance.account_manager_flag = json_data.get('accountManagerFlag')
        instance.tech_flag = json_data.get('techFlag')
        instance.sales_flag = json_data.get('salesFlag')

    def get_page(self, *args, **kwargs):
        return self.client.get_company_team_role(*args, **kwargs)


class ContactSynchronizer(Synchronizer):
    client_class = api.CompanyAPIClient
    model_class = models.ContactTracker

    related_meta = {
        'company': (models.Company, 'company'),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_conditions = ['inactiveFlag=False']

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.first_name = json_data.get('firstName')
        instance.last_name = json_data.get('lastName')
        instance.title = json_data.get('title')
        self.set_relations(instance, json_data)

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_contacts(*args, **kwargs)

    def get_single(self, contact_id):
        return self.client.get_single_contact(contact_id)

    def fetch_sync_by_id(self, instance_id, sync_config={}):
        instance = super().fetch_sync_by_id(instance_id)
        self.sync_related(instance)
        return instance

    def sync_related(self, instance):
        instance_id = instance.id
        sync_classes = []

        settings = DjconnectwiseSettings().get_settings()
        if settings['sync_contact_communications']:
            contact_communication_sync = ContactCommunicationSynchronizer()
            contact_communication_sync.sync_single_id = instance_id
            sync_classes.append((contact_communication_sync,
                                 Q(contact=instance_id)))
            self.sync_children(*sync_classes)


class ContactCommunicationSynchronizer(ChildFetchRecordsMixin, Synchronizer):
    client_class = api.CompanyAPIClient
    model_class = models.ContactCommunicationTracker
    parent_model_class = models.Contact

    related_meta = {
        'type': (models.CommunicationType, 'type'),
    }

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.value = json_data.get('value')
        instance.extension = json_data.get('extension')
        instance.default_flag = json_data.get('defaultFlag')
        contact_id = json_data.get('contactId')

        if contact_id:
            try:
                related_contact = models.Contact.objects.get(pk=contact_id)
                setattr(instance, 'contact', related_contact)
            except ObjectDoesNotExist as e:
                logger.warning(
                    'Contact not found for {}.'.format(instance.id) +
                    ' ObjectDoesNotExist Exception: {}.'.format(e)
                )

        self.set_relations(instance, json_data)
        return instance

    def client_call(self, contact_id, *args, **kwargs):
        return self.client.get_contact_communications(contact_id, *args,
                                                      **kwargs)

    def get_single(self, communication_id):
        return self.client.get_single_communication(communication_id)


class CommunicationTypeSynchronizer(Synchronizer):
    client_class = api.CompanyAPIClient
    model_class = models.CommunicationTypeTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.description = json_data.get('description')
        instance.phone_flag = json_data.get('phoneFlag')
        instance.fax_flag = json_data.get('faxFlag')
        instance.email_flag = json_data.get('emailFlag')
        instance.default_flag = json_data.get('defaultFlag')
        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_communication_types(*args, **kwargs)


class MyCompanyOtherSynchronizer(Synchronizer):
    client_class = api.SystemAPIClient
    model_class = models.MyCompanyOtherTracker

    related_meta = {
        'defaultCalendar': (models.Calendar, 'default_calendar'),
    }

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        self.set_relations(instance, json_data)
        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_mycompanyother(*args, **kwargs)


class ActivityStatusSynchronizer(Synchronizer):
    client_class = api.SalesAPIClient
    model_class = models.ActivityStatusTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        instance.default_flag = json_data.get('defaultFlag', False)
        instance.inactive_flag = json_data.get('inactiveFlag', False)
        instance.spawn_followup_flag = \
            json_data.get('spawnFollowupFlag', False)
        instance.closed_flag = json_data.get('closedFlag', False)
        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_activity_statuses(*args, **kwargs)


class ActivityTypeSynchronizer(Synchronizer):
    client_class = api.SalesAPIClient
    model_class = models.ActivityTypeTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        instance.points = json_data.get('points')
        instance.default_flag = json_data.get('defaultFlag', False)
        instance.inactive_flag = json_data.get('inactiveFlag', False)
        instance.email_flag = json_data.get('emailFlag', False)
        instance.memo_flag = json_data.get('memoFlag', False)
        instance.history_flag = json_data.get('historyFlag', False)

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_activity_types(*args, **kwargs)


class ActivitySynchronizer(UpdateRecordMixin, Synchronizer):
    client_class = api.SalesAPIClient
    model_class = models.ActivityTracker

    related_meta = {
        'opportunity': (models.Opportunity, 'opportunity'),
        'ticket': (models.Ticket, 'ticket'),
        'assignTo': (models.Member, 'assign_to'),
        'status': (models.ActivityStatus, 'status'),
        'type': (models.ActivityType, 'type'),
        'company': (models.Company, 'company'),
        'contact': (models.Contact, 'contact'),
        'agreement': (models.Agreement, 'agreement'),
    }

    API_FIELD_NAMES = {
        'name': 'name',
        'status': 'status',
        'notes': 'notes',
        'type': 'type',
        'assign_to': 'assignTo',
        'company': 'company',
        'contact': 'contact',
        'agreement': 'agreement',
        'opportunity': 'opportunity',
        'ticket': 'ticket',
        'date_start': 'dateStart',
        'date_end': 'dateEnd',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only sync activities in non-closed statuses. There shouldn't be
        # too many activity statuses so we don't need to page this like we
        # do with tickets.
        self.api_conditions = ['status/id in ({})'.format(
            ','.join(
                [
                    str(i.id) for
                    i in models.ActivityStatus.objects.filter(
                        closed_flag=False
                    )
                ]
            )
        )]

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        notes = json_data.get('notes')
        if notes:
            instance.notes = normalize_newlines(notes)

        # handle dates.  Assume UTC timezone when not defined
        # (according to ConnectWise FAQ: "What DateTimes are supported?")
        date_start = json_data.get('dateStart')
        if date_start:
            instance.date_start = parse(date_start, default=parse('00:00Z'))

        date_end = json_data.get('dateEnd')
        if date_end:
            instance.date_end = parse(date_end, default=parse('00:00Z'))

        # Creating activities in the ConnectWise UI and API requires that
        # the 'assignTo' field is set. But we've seen cases where
        # 'assignTo' is null. So skip the activity if it's 'assignTo' is null.
        assign_to_id = json_data.get('assignTo')
        if not assign_to_id:
            raise InvalidObjectException(
                'Activity {} has a null assignTo field - '
                'skipping.'.format(instance.id)
            )

        instance.udf = {str(item['id']): item
                        for item in json_data.get('customFields', list())}

        self.set_relations(instance, json_data)
        return instance

    def update_record(self, client, record, api_fields):
        return client.update_activity(record, api_fields)

    def get_page(self, *args, **kwargs):
        return self.client.get_activities(*args, **kwargs)

    def get_single(self, activity_id):
        return self.client.get_single_activity(activity_id)


class SalesProbabilitySynchronizer(Synchronizer):
    client_class = api.SalesAPIClient
    model_class = models.SalesProbabilityTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.probability = json_data.get('probability')

    def get_page(self, *args, **kwargs):
        return self.client.get_probabilities(*args, **kwargs)


class ScheduleEntriesSynchronizer(BatchConditionMixin, Synchronizer):
    client_class = api.ScheduleAPIClient
    model_class = models.ScheduleEntryTracker
    batch_condition_list = []

    related_meta = {
        'where': (models.Location, 'where'),
        'status': (models.ScheduleStatus, 'status'),
        'type': (models.ScheduleType, 'schedule_type'),
        'member': (models.Member, 'member')
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.settings = DjconnectwiseSettings().get_settings()
        self.no_batch = kwargs.get('no_batch')

        self.api_conditions = [
            "(type/identifier='S' or type/identifier='O' "
            "or type/identifier='C')"
        ]

        if not self.no_batch:
            self.api_conditions.append("doneFlag=false")

            # Only get schedule entries for tickets or opportunities that we
            # already have in the DB.
            ticket_ids = set(
                models.Ticket.objects.order_by(
                    self.lookup_key).values_list('id', flat=True)
            )
            opportunity_ids = set(
                models.Opportunity.objects.order_by(
                    self.lookup_key).values_list('id', flat=True)
            )
            activity_ids = set(
                models.Activity.objects.order_by(
                    self.lookup_key).values_list('id', flat=True)
            )
            self.batch_condition_list = \
                list(ticket_ids | opportunity_ids | activity_ids)

    def get(self, results, conditions=None):

        if self.no_batch:
            self.fetch_records(results, conditions)
        else:
            super().get(results, conditions)

        return results

    def get_optimal_size(self, condition_list, max_url_length=2000,
                         min_url_length=None):
        object_id_size = self.settings['schedule_entry_conditions_size']

        return object_id_size if object_id_size \
            else super().get_optimal_size(condition_list, max_url_length,
                                          min_url_length)

    def get_batch_condition(self, conditions):
        return 'objectId in ({})'.format(
            ','.join([str(i) for i in conditions])
        )

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        instance.done_flag = json_data['doneFlag']

        # Handle member- there are cases where no member field is provided,
        # which we consider invalid.
        if 'member' not in json_data:
            raise InvalidObjectException(
                'Schedule entry {} has no member field- skipping.'
                .format(instance.id)
            )

        try:
            member_id = json_data['member'].get('id')
            models.Member.objects.get(pk=member_id)
        except ObjectDoesNotExist:
            raise InvalidObjectException(
                'Schedule entry {} can not find member: {}'
                '- skipping.'.format(instance.id, member_id)
            )

        # handle dates
        # Connectwise handles schedule entries with a date and no time by
        # leaving it as midnight UTC. This has the unfortunate side effect of
        # looking like a completely valid time in other time zones. Ex, In
        # UTC-8 it looks like 4pm - 4pm. Alter these midnight datetimes to
        # appear as midnight in the local time, instead of midnight UTC.
        date_start = json_data.get('dateStart')
        if date_start:
            instance.date_start = parse(date_start)

            date_end = json_data.get('dateEnd')

            if instance.date_start.time() == datetime.time(0, 0) \
                    and json_data.get('hours') == 0.0:
                instance.date_start = parse(date_start) - \
                    timezone.localtime().utcoffset()
                if date_end:
                    instance.date_end = parse(date_end) - \
                        timezone.localtime().utcoffset()
            elif date_end:
                instance.date_end = parse(date_end)

        self.set_relations(instance, json_data)

        ticket_class = models.Ticket
        activity_class = models.Activity
        try:
            uid = json_data.get('objectId')
        except AttributeError:
            raise InvalidObjectException(
                'Schedule entry {} has no objectId key to find its target'
                '- skipping.'.format(instance.id)
            )

        if json_data['type'].get('identifier') == "S":
            try:
                related_ticket = ticket_class.objects.get(pk=uid)
                if json_data.get('doneFlag'):
                    setattr(instance, 'ticket_object', None)
                else:
                    setattr(instance, 'ticket_object', related_ticket)
            except ObjectDoesNotExist as e:
                logger.warning(
                    'Ticket not found for {}.'.format(instance.id) +
                    ' ObjectDoesNotExist Exception: {}.'.format(e)
                )
        elif json_data['type'].get('identifier') == "C":
            try:
                related_activity = activity_class.objects.get(pk=uid)
                setattr(instance, 'activity_object', related_activity)
            except ObjectDoesNotExist as e:
                logger.warning(
                    'Activity not found for {}.'.format(instance.id) +
                    ' ObjectDoesNotExist Exception: {}.'.format(e)
                )
        else:
            raise InvalidObjectException(
                'Invalid ScheduleEntry type for schedule entry {}- skipping.'
                .format(instance.id)
            )

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_schedule_entries(*args, **kwargs)

    def get_single(self, entry_id):
        return self.client.get_schedule_entry(entry_id)

    def fetch_sync_by_condition(self, conditions):
        synced_entries = []
        api_entries = self.client.get_schedule_entries(conditions=conditions)

        for entry in api_entries:
            instance, _ = self.update_or_create_instance(entry)
            synced_entries.append(instance)

        return synced_entries

    def create_new_entry(self, target, **kwargs):
        """
        Send POST request to ConnectWise to create a new entry and then
        create it in the local database from the response

        """
        schedule_client = api.ScheduleAPIClient(
            api_public_key=kwargs.get('api_public_key'),
            api_private_key=kwargs.get('api_private_key')
        )
        # Type defines if it is a service ticket, opportunity, or activity.
        # (There are more but we probably wont be using them).
        # In the context of schedule entry types, Service Tickets and
        # Project tickets are the same.
        schedule_type = models.ScheduleType.objects.get(
            identifier=target.SCHEDULE_ENTRY_TYPE)

        instance = schedule_client.post_schedule_entry(
            target, schedule_type, **kwargs)
        return self.update_or_create_instance(instance)

    def update_entry(self, **kwargs):
        """
        Send PATCH request to ConnectWise to update an entry and then
        update it in the local database from the response
        """
        schedule_client = api.ScheduleAPIClient()
        instance = schedule_client.patch_schedule_entry(**kwargs)
        return self.update_or_create_instance(instance)


class ScheduleStatusSynchronizer(Synchronizer):
    client_class = api.ScheduleAPIClient
    model_class = models.ScheduleStatusTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_schedule_statuses(*args, **kwargs)


class ScheduleTypeSynchronizer(Synchronizer):
    client_class = api.ScheduleAPIClient
    model_class = models.ScheduleTypeTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        instance.identifier = json_data.get('identifier')

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_schedule_types(*args, **kwargs)


class TerritorySynchronizer(Synchronizer):
    client_class = api.SystemAPIClient
    model_class = models.TerritoryTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_territories(*args, **kwargs)


class TimeEntrySynchronizer(BatchConditionMixin,
                            CallbackSyncMixin, Synchronizer):
    client_class = api.TimeAPIClient
    model_class = models.TimeEntryTracker
    batch_condition_list = []

    related_meta = {
        'company': (models.Company, 'company'),
        'member': (models.Member, 'member')
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_conditions = [
            "(chargeToType='ServiceTicket' OR chargeToType='ProjectTicket')"
        ]
        # Only get time entries for tickets that are already in the DB
        # Possibly Activities also in the future
        ticket_ids = set(
            models.Ticket.objects.order_by(
                self.lookup_key).values_list('id', flat=True)
        )
        self.batch_condition_list = list(ticket_ids)

    def get_batch_condition(self, conditions):
        return 'chargeToId in ({})'.format(
            ','.join([str(i) for i in conditions])
        )

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.charge_to_type = json_data.get('chargeToType')
        instance.billable_option = json_data.get('billableOption')

        notes = json_data.get('notes')
        if notes:
            instance.notes = normalize_newlines(notes)
        instance.internal_notes = json_data.get('internalNotes')

        time_start = json_data.get('timeStart')
        if time_start:
            instance.time_start = parse(time_start, default=parse('00:00Z'))

        time_end = json_data.get('timeEnd')
        if time_end:
            instance.time_end = parse(time_end, default=parse('00:00Z'))

        # Since django's `to_python` method builds the record from the DB
        # by creating the decimal using a string we must also do this.
        # Normally it would not matter too much, but since we want to compare
        # them exactly it must be done this way. Otherwise due to floating
        # point errors the decimal we create with a float vs a string will
        # be different and fail comparison in the FieldTracker.
        hours_deduct = json_data.get('hoursDeduct')
        instance.hours_deduct = Decimal(str(hours_deduct)) \
            if hours_deduct is not None else None

        actual_hours = json_data.get('actualHours')
        instance.actual_hours = Decimal(str(actual_hours)) \
            if actual_hours is not None else None

        detail_description_flag = json_data.get('addToDetailDescriptionFlag')
        if detail_description_flag:
            instance.detail_description_flag = detail_description_flag

        internal_analysis_flag = json_data.get('addToInternalAnalysisFlag')
        if internal_analysis_flag:
            instance.internal_analysis_flag = internal_analysis_flag

        resolution_flag = json_data.get('addToResolutionFlag')
        if resolution_flag:
            instance.resolution_flag = resolution_flag

        self.set_relations(instance, json_data)

        # Similar to Schedule Entries, chargeToId is stored as an int in
        # ConnectWise, handled as special situation.
        # Not making a method to handle this in a similar way to Schedule
        # entries and even with the similar code as this may be VERY
        # different in the near future, because charge_to_id would be
        # converted to a GenericForeignKey and would be handled differently.
        ticket_class = models.Ticket
        try:
            charge_id = json_data['chargeToId']
        except KeyError:
            raise InvalidObjectException(
                'Time Entry {} has no chargeToId key to find its target'
                '- skipping.'.format(instance.id)
            )

        try:
            related_ticket = ticket_class.objects.get(pk=charge_id)
            setattr(instance, 'charge_to_id', related_ticket)
        except ObjectDoesNotExist as e:
            logger.warning(
                'Ticket not found for {}.'.format(instance.id) +
                ' ObjectDoesNotExist Exception: {}.'.format(e)
            )

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_time_entries(*args, **kwargs)

    def create_new_entry(self, target, **kwargs):
        """
        Send POST request to ConnectWise to create a new entry and then
        create it in the local database from the response
        """
        target_data = {}
        if isinstance(target, models.Ticket):
            target_data['id'] = target.id
            record_type = target.record_type

            # ConnectWise doesn't allow "ProjectIssue" as a valid chargeToType.
            # See https://developer.connectwise.com/Products/Manage/REST#/TimeEntries # noqa
            # for valid chargeToTypes.
            if record_type == models.Ticket.PROJECT_ISSUE:
                record_type = models.Ticket.PROJECT_TICKET

            target_data['type'] = record_type
        else:
            raise InvalidObjectException(
                "Invalid target type for TimeEntry "
                "creation: " + str(target.__class__) + "."
            )

        time_client = api.TimeAPIClient(
            api_public_key=kwargs.get('api_public_key'),
            api_private_key=kwargs.get('api_private_key')
        )
        instance = time_client.post_time_entry(target_data, **kwargs)
        return self.update_or_create_instance(instance)


class LocationSynchronizer(Synchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.LocationTracker

    def _assign_field_data(self, location, location_json):
        """
        Assigns field data from an company_json instance
        to a local Company model instance
        """
        location.id = location_json.get('id')
        location.name = location_json.get('name')
        location.where = location_json.get('where')
        return location

    def get_page(self, *args, **kwargs):
        return self.client.get_locations(*args, **kwargs)


class PrioritySynchronizer(Synchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.TicketPriorityTracker

    def _assign_field_data(self, ticket_priority, api_priority):
        ticket_priority.id = api_priority.get('id')
        ticket_priority.name = api_priority.get('name')
        ticket_priority.color = api_priority.get('color')

        # work around due to api data inconsistencies
        sort_value = api_priority.get('sort') or api_priority.get('sortOrder')
        if sort_value:
            ticket_priority.sort = sort_value

        return ticket_priority

    def get_page(self, *args, **kwargs):
        return self.client.get_priorities(*args, **kwargs)


class ProjectNotesSynchronizer(Synchronizer):
    client_class = api.ProjectAPIClient

    def get_notes(self, project_id, *args, **kwargs):
        return self.client.get_project_notes(project_id, *args, **kwargs)

    def get_count(self, project_id):
        return self.client.get_project_notes_count(project_id)


class ProjectStatusSynchronizer(Synchronizer):

    client_class = api.ProjectAPIClient
    model_class = models.ProjectStatusTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        instance.default_flag = json_data.get('defaultFlag')
        instance.inactive_flag = json_data.get('inactiveFlag')
        instance.closed_flag = json_data.get('closedFlag')
        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_project_statuses(*args, **kwargs)


class ProjectPhaseSynchronizer(ChildFetchRecordsMixin, Synchronizer):
    client_class = api.ProjectAPIClient
    model_class = models.ProjectPhaseTracker
    parent_model_class = models.Project

    related_meta = {
        'board': (models.ConnectWiseBoard, 'board')
    }

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.description = json_data.get('description')
        instance.notes = json_data.get('notes')
        instance.wbs_code = json_data.get('wbsCode')
        scheduled_hours = json_data.get('scheduledHours')
        budget_hours = json_data.get('budgetHours')
        actual_hours = json_data.get('actualHours')
        instance.budget_hours = Decimal(str(budget_hours)) \
            if budget_hours is not None else None
        instance.actual_hours = Decimal(str(actual_hours)) \
            if actual_hours is not None else None
        instance.scheduled_hours = Decimal(str(scheduled_hours)) \
            if scheduled_hours is not None else None

        if json_data.get('billTime') == 'NoDefault':
            instance.bill_time = None
        else:
            instance.bill_time = json_data.get('billTime')

        scheduled_start = json_data.get('scheduledStart')
        scheduled_end = json_data.get('scheduledEnd')
        actual_start = json_data.get('actualStart')
        actual_end = json_data.get('actualEnd')
        required_date = json_data.get('deadlineDate')

        if scheduled_start:
            instance.scheduled_start = parse(scheduled_start).date()

        if scheduled_end:
            instance.scheduled_end = parse(scheduled_end).date()

        if actual_start:
            instance.actual_start = parse(actual_start).date()

        if actual_end:
            instance.actual_end = parse(actual_end).date()

        if required_date:
            instance.required_date = parse(required_date).date()

        try:
            project_id = json_data.get('projectId')
            related_project = models.Project.objects.get(pk=project_id)
            setattr(instance, 'project', related_project)
        except models.Project.DoesNotExist:
            raise InvalidObjectException(
                'Project phase {} has no projectId key to find its target'
                '- skipping.'.format(instance.id)
            )
        except ObjectDoesNotExist as e:
            raise InvalidObjectException(
                'Project phase {} has a projectId that does not exist.'
                ' ObjectDoesNotExist Exception: {}'.format(instance.id, e)
            )

        self.set_relations(instance, json_data)
        return instance

    def client_call(self, project_id, *args, **kwargs):
        return self.client.get_project_phases(project_id, *args, **kwargs)


class ProjectTypeSynchronizer(Synchronizer):
    client_class = api.ProjectAPIClient
    model_class = models.ProjectTypeTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        instance.default_flag = json_data.get('defaultFlag')
        instance.inactive_flag = json_data.get('inactiveFlag')
        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_project_types(*args, **kwargs)


class ProjectTeamMemberSynchronizer(ChildFetchRecordsMixin, Synchronizer):
    client_class = api.ProjectAPIClient
    model_class = models.ProjectTeamMemberTracker
    parent_model_class = models.Project

    related_meta = {
        'member': (models.Member, 'member'),
        'workRole': (models.WorkRole, 'work_role'),
        'projectRole': (models.ProjectRole, 'project_role')
    }

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        start_date = json_data.get('startDate')
        end_date = json_data.get('endDate')

        if start_date:
            instance.start_date = parse(start_date)
        if end_date:
            instance.end_date = parse(end_date)

        try:
            project_id = json_data.get('projectId')
            related_project = models.Project.objects.get(pk=project_id)
            setattr(instance, 'project', related_project)
        except ObjectDoesNotExist as e:
            raise InvalidObjectException(
                'Project team member {} has a projectId that does not exist.'
                ' ObjectDoesNotExist Exception: {}'.format(instance.id, e)
            )

        self.set_relations(instance, json_data)
        return instance

    def client_call(self, project_id, *args, **kwargs):
        return self.client.get_project_team_members(
            project_id, *args, **kwargs)

    @property
    def parent_object_ids(self):
        return self.parent_model_class.objects.filter(
            status__closed_flag=False).order_by(
            self.lookup_key).values_list(self.lookup_key, flat=True)


class ProjectSynchronizerMixin(BatchConditionMixin):
    def get_batch_condition(self, conditions):
        batch_condition = 'status/id in ({})'.format(
            ','.join([str(i) for i in conditions])
        )

        request_settings = DjconnectwiseSettings().get_settings()
        keep_closed = request_settings.get('keep_closed_ticket_days')
        if keep_closed and self.full:
            batch_condition = self.format_conditions(
                keep_closed, batch_condition, request_settings
            )

        return batch_condition

    def format_conditions(self, keep_closed,
                          batch_condition, request_settings):
        closed_date = timezone.now() - timezone.timedelta(days=keep_closed)
        condition = 'lastUpdated>[{}]'.format(closed_date)

        keep_closed_board_ids = \
            request_settings.get('keep_closed_status_board_ids')
        if keep_closed_board_ids:
            condition = '{} and board/id in ({})'.format(
                condition, ','.join(map(str, keep_closed_board_ids))
            )

        batch_condition = '{} or {}'.format(batch_condition, condition)
        return batch_condition


class ProjectSynchronizer(CreateRecordMixin,
                          UpdateRecordMixin, ProjectSynchronizerMixin,
                          Synchronizer):
    client_class = api.ProjectAPIClient
    model_class = models.ProjectTracker
    batch_condition_list = []
    related_meta = {
        'status': (models.ProjectStatus, 'status'),
        'manager': (models.Member, 'manager'),
        'company': (models.Company, 'company'),
        'contact': (models.Contact, 'contact'),
        'type': (models.ProjectType, 'type'),
        'board': (models.ConnectWiseBoard, 'board'),
    }

    API_FIELD_NAMES = {
        'name': 'name',
        'estimated_start': 'estimatedStart',
        'estimated_end': 'estimatedEnd',
        'percent_complete': 'percentComplete',
        'type': 'type',
        'status': 'status',
        'manager': 'manager',
        'contact': 'contact',
        'description': 'description',
        'billing_method': 'billingMethod',
        'company': 'company',
        'board': 'board',
        'company': 'company',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        filtered_statuses = \
            models.ProjectStatus.objects.filter(closed_flag=False)

        if self.full:
            self.api_conditions = ['status/id in ({})'.format(
                ','.join(str(i.id) for i in filtered_statuses)
            )]

        if filtered_statuses:
            self.batch_condition_list = \
                list(filtered_statuses.values_list('id', flat=True))

    def _assign_field_data(self, instance, json_data):
        actual_start = json_data.get('actualStart')
        actual_end = json_data.get('actualEnd')
        required_date = json_data.get('deadlineDate')
        estimated_start = json_data.get('estimatedStart')
        estimated_end = json_data.get('estimatedEnd')
        scheduled_start = json_data.get('scheduledStart')
        scheduled_end = json_data.get('scheduledEnd')

        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        instance.billing_method = json_data.get('billingMethod')
        description = json_data.get('description')
        if description:
            instance.description = normalize_newlines(description)

        actual_hours = json_data.get('actualHours')
        budget_hours = json_data.get('budgetHours')
        scheduled_hours = json_data.get('scheduledHours')
        percent_complete = json_data.get('percentComplete')
        instance.udf = {str(item['id']): item
                        for item in json_data.get('customFields', list())}

        instance.actual_hours = Decimal(str(actual_hours)) \
            if actual_hours is not None else None
        instance.budget_hours = Decimal(str(budget_hours)) \
            if budget_hours is not None else None
        instance.scheduled_hours = Decimal(str(scheduled_hours)) \
            if scheduled_hours is not None else None
        instance.percent_complete = Decimal(str(percent_complete)) \
            if percent_complete is not None else None

        if actual_start:
            instance.actual_start = parse(actual_start).date()

        if actual_end:
            instance.actual_end = parse(actual_end).date()

        if required_date:
            instance.required_date = parse(required_date).date()

        if estimated_start:
            instance.estimated_start = parse(estimated_start).date()

        if estimated_end:
            instance.estimated_end = parse(estimated_end).date()

        if scheduled_start:
            instance.scheduled_start = parse(scheduled_start).date()

        if scheduled_end:
            instance.scheduled_end = parse(scheduled_end).date()

        self.set_relations(instance, json_data)
        return instance

    def create_record(self, client, api_fields):
        return client.create_project(api_fields)

    def update_record(self, client, record, api_fields):
        return client.update_project(record, api_fields)

    def get_page(self, *args, **kwargs):
        return self.client.get_projects(*args, **kwargs)

    def get_single(self, project_id):
        return self.client.get_project(project_id)


class MemberSynchronizer(Synchronizer):
    client_class = api.SystemAPIClient
    model_class = models.MemberTracker
    bulk_prune = False

    related_meta = {
        'workRole': (models.WorkRole, 'work_role'),
        'workType': (models.WorkType, 'work_type')
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_sync_job_time = None

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.first_name = json_data.get('firstName')
        instance.last_name = json_data.get('lastName')
        instance.identifier = json_data.get('identifier')
        instance.office_email = json_data.get('officeEmail')
        instance.license_class = json_data.get('licenseClass')
        instance.inactive = json_data.get('inactiveFlag')
        instance.title = json_data.get('title')

        self.set_relations(instance, json_data)

        return instance

    def _save_avatar(self, member, avatar, attachment_filename):
        """
        Thumbnails will only be generated if the filename hashed from the
        avatar is not the same as the currently saved avatar or the avatar
        does not exist in storage already.
        """
        thumbnail_size = {
            'avatar': (80, 80),
            'micro_avatar': (20, 20),
        }
        extension = get_filename_extension(attachment_filename)
        filename = '{}.{}'.format(get_hash(avatar), extension)

        current_avatar = member.avatar
        current_avatar_filename = '{}20x20.{}'.format(member.avatar, extension)
        process_thumbnails = filename != current_avatar

        if process_thumbnails or \
                not default_storage.exists(current_avatar_filename):
            member.avatar = filename
            avatar_file = None
            for size in thumbnail_size:
                current_filename = generate_filename(thumbnail_size[size],
                                                     current_avatar, extension)
                filename = '{}.{}'.format(get_hash(avatar), extension)
                try:
                    avatar_file, filename = generate_thumbnail(
                        avatar, thumbnail_size[size],
                        extension, filename)

                    # Just delete the currently saved avatar image
                    # so we don't need to worry about cleaning up
                    # duplicates or old thumbnails
                    if avatar_file and filename:
                        default_storage.delete(current_filename)

                        logger.info("Saving member '{}' avatar to {}.".format(
                            member.identifier, filename))
                        default_storage.save(filename, avatar_file)
                    else:
                        # If there were any problems saving the avatar clear
                        # the filename from the member
                        member.avatar = ""
                except NoCredentialsError as e:
                    # NoCredentialsError should be raised
                    e.fmt = 'During saving member avatar: ' + e.fmt
                    raise e
                except Exception as e:
                    logger.warning("Error saving member avatar. {}".format(e))

    def get_page(self, *args, **kwargs):
        return self.client.get_members(*args, **kwargs)

    def update_or_create_instance(self, api_instance):
        """
        In addition to what the parent does, also update avatar if necessary.
        """
        try:
            instance, result = super().update_or_create_instance(api_instance)
        except IntegrityError as e:
            raise InvalidObjectException(
                'Failed to update member: {}'.format(e)
            )
        username = instance.identifier
        photo_id = None

        # Only update the avatar if the member profile
        # was updated since last sync.
        member_last_updated = parse(api_instance['_info']['lastUpdated'])
        member_stale = False
        if self.last_sync_job_time:
            member_stale = member_last_updated > self.last_sync_job_time

        if api_instance.get('photo'):
            photo_id = api_instance['photo']['id']

        # For when a CW user removes their photo without setting
        # a new one. Remove the image from storage.
        if instance.avatar and not photo_id:
            try:
                remove_thumbnail(instance.avatar)
            except NoCredentialsError as e:
                msg = 'Error when removing thumbnail for {}.' \
                      ' NoCredentialsError Exception: {}.' \
                    .format(instance.username, e)
                logger.warning(msg)
            instance.avatar = None
            instance.save()
        # Fetch the image when:
        # CW tells us where the image is AND one of the following is true:
        # * this is a full sync
        # * there's no previous member sync job record
        # * the member's avatar doesn't already exist
        # * our member record is stale
        # * the member was created
        if photo_id and (self.full or
                         not self.last_sync_job_time or
                         not bool(instance.avatar) or
                         member_stale or
                         result == CREATED):
            logger.info(
                'Fetching avatar for member {}.'.format(username)
            )
            (attachment_filename, avatar) = self.client \
                .get_member_image_by_photo_id(photo_id, username)
            if attachment_filename and avatar:
                try:
                    self._save_avatar(instance, avatar, attachment_filename)
                except NoCredentialsError as e:
                    msg = 'Error when saving avatar for {}.' \
                          ' NoCredentialsError Exception: {}.' \
                          .format(username, e)
                    logger.warning(msg)
                    # If there were any problems saving the avatar clear the
                    # filename from the member
                    instance.avatar = ""
            instance.save()

        return instance, result


class TicketSynchronizerMixin:
    model_class = models.TicketTracker
    batch_condition_list = []

    related_meta = {
        'team': (models.Team, 'team'),
        'board': (models.ConnectWiseBoard, 'board'),
        'company': (models.Company, 'company'),
        'contact': (models.Contact, 'contact'),
        'priority': (models.TicketPriority, 'priority'),
        'project': (models.Project, 'project'),
        'phase': (models.ProjectPhase, 'phase'),
        'serviceLocation': (models.Location, 'location'),
        'status': (models.BoardStatus, 'status'),
        'owner': (models.Member, 'owner'),
        'type': (models.Type, 'type'),
        'subType': (models.SubType, 'sub_type'),
        'item': (models.Item, 'sub_type_item'),
        'agreement': (models.Agreement, 'agreement'),
        'source': (models.Source, 'source'),
        'workType': (models.WorkType, 'work_type'),
        'workRole': (models.WorkRole, 'work_role'),
        'site': (models.CompanySite, 'company_site'),
    }

    API_FIELD_NAMES = {
        'summary': 'summary',
        'required_date_utc': 'requiredDate',
        'estimated_start_date': 'estimatedStartDate',
        'budget_hours': 'budgetHours',
        'closed_flag': 'closedFlag',
        'owner': 'owner',
        'type': 'type',
        'sub_type': 'subType',
        'sub_type_item': 'item',
        'agreement': 'agreement',
        'status': 'status',
        'priority': 'priority',
        'board': 'board',
        'company': 'company',
        'location': 'location',
        'contact': 'contact',
        'contact_name': 'contactName',
        'contact_phone_number': 'contactPhoneNumber',
        'contact_email_address': 'contactEmailAddress',
        'automatic_email_resource_flag': 'automaticEmailResourceFlag',
        'automatic_email_cc_flag': 'automaticEmailCcFlag',
        'automatic_email_contact_flag': 'automaticEmailContactFlag',
        'automatic_email_cc': 'automaticEmailCc',
        'source': 'source',
        'is_issue_flag': 'isIssueFlag',
        'customer_updated': 'customerUpdatedFlag',
        'initial_description': 'initialDescription',
        'project': 'project',
        'phase': 'phase',
        'team': 'team',
        'company_site': 'site',
        'ticket_predecessor': 'predecessorId',
        'predecessor_type': 'predecessorType'
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.full:
            self.api_conditions = ['closedFlag=False']
        # To get all open tickets, we can simply supply a `closedFlag=False`
        # condition for on-premise ConnectWise. But for hosted ConnectWise,
        # this results in timeouts for requests, so we also need to add a
        # condition for all the open statuses. This doesn't impact on-premise
        # ConnectWise, so we just do it for all cases.
        request_settings = DjconnectwiseSettings().get_settings()
        board_ids = request_settings.get('board_status_filter')

        filtered_statuses = models.BoardStatus.available_objects.filter(
            closed_status=False).order_by(self.lookup_key)

        if board_ids:
            boards_exist = models.ConnectWiseBoard.available_objects.filter(
                id__in=board_ids).exists()

            if boards_exist:
                filtered_statuses = filtered_statuses.filter(
                    board__id__in=board_ids
                )

        if filtered_statuses:
            # Only do this if we know of at least one open status.
            self.batch_condition_list = \
                list(filtered_statuses.values_list('id', flat=True))

    def get_batch_condition(self, conditions):
        batch_condition = 'status/id in ({})'.format(
            ','.join([str(i) for i in conditions])
        )

        request_settings = DjconnectwiseSettings().get_settings()
        keep_closed = request_settings.get('keep_closed_ticket_days')
        if keep_closed:
            batch_condition = self.format_conditions(
                keep_closed, batch_condition, request_settings)

        return batch_condition

    def format_conditions(self, keep_closed,
                          batch_condition, request_settings):
        closed_date = timezone.now() - timezone.timedelta(days=keep_closed)
        condition = 'closedDate>[{}]'.format(closed_date)

        keep_closed_board_ids = \
            request_settings.get('keep_closed_status_board_ids')
        if keep_closed_board_ids:
            condition = '{} and board/id in ({})'.format(
                condition, keep_closed_board_ids)

        # lastUpdated is only present when running partial syncs.
        if not self.full and self.api_conditions:
            last_updated = self.api_conditions[-1]
            condition = '{} and {}'.format(condition, last_updated)

        batch_condition = '{} or {}'.format(batch_condition, condition)
        return batch_condition

    def get_page(self, *args, **kwargs):
        return self.client.get_tickets(*args, **kwargs)

    def get_single(self, ticket_id):
        return self.client.get_ticket(ticket_id)

    # sync_config is read-only, so mutable argument is used for simplicity.
    def sync_related(self, instance, sync_config={}, result=None):
        instance_id = instance.id
        sync_classes = []

        if sync_config.get('sync_service_note', True):
            note_sync = ServiceNoteSynchronizer()
            note_sync.sync_single_id = instance_id
            if result == CREATED:
                note_sync.sync_all = True

            sync_classes.append((note_sync, Q(ticket=instance)))

        if sync_config.get('sync_time_entry', True):
            time_sync = TimeEntrySynchronizer()
            if result == CREATED:
                time_sync.sync_all = True

            time_sync.batch_condition_list = [instance_id]
            sync_classes.append((time_sync, Q(charge_to_id=instance)))

        if sync_config.get('sync_activity', True):
            activity_sync = ActivitySynchronizer()
            activity_sync.api_conditions = ['ticket/id={}'.format(instance_id)]
            sync_classes.append((activity_sync, Q(ticket=instance)))

        self.task_synchronizer_class().sync_items(instance)

        self.sync_children(*sync_classes)

    def fetch_sync_by_id(self, instance_id, sync_config={}):
        api_instance = self.get_single(instance_id)
        instance, result = self.update_or_create_instance(api_instance)

        if not instance.closed_flag:
            self.sync_related(instance, sync_config, result)
        return instance

    def _instance_ids(self, filter_params=None):
        tickets_qset = self.filter_by_record_type().order_by(self.lookup_key)

        if not filter_params:
            ids = tickets_qset.values_list(self.lookup_key, flat=True)
        else:
            ids = tickets_qset.filter(filter_params).values_list(
                self.lookup_key, flat=True
            )
        return set(ids)

    def get_delete_qset(self, stale_ids):
        tickets = self.filter_by_record_type()
        return tickets.filter(pk__in=stale_ids)

    def get_sync_job_qset(self):
        return models.SyncJob.objects.filter(
            entity_name=self.model_class.__bases__[0].__name__,
            synchronizer_class=self.__class__.__name__
        )

    def _assign_field_data(self, instance, json_data):

        instance.id = json_data.get('id')
        instance.summary = json_data.get('summary')
        instance.closed_flag = json_data.get('closedFlag')
        instance.entered_date_utc = json_data.get('_info').get('dateEntered')
        instance.last_updated_utc = json_data.get('_info').get('lastUpdated')
        instance.required_date_utc = json_data.get('requiredDate')
        instance.resources = json_data.get('resources')
        instance.bill_time = json_data.get('billTime')
        instance.customer_updated = json_data.get('customerUpdatedFlag')
        instance.estimated_start_date = json_data.get('estimatedStartDate')

        if instance.entered_date_utc:
            # Parse the date here so that a datetime object is
            # available for SLA parsing.
            instance.entered_date_utc = parse(instance.entered_date_utc)
        if instance.last_updated_utc:
            instance.last_updated_utc = parse(instance.last_updated_utc)
        if instance.required_date_utc:
            instance.required_date_utc = parse(instance.required_date_utc)
        if instance.estimated_start_date:
            instance.estimated_start_date = \
                parse(instance.estimated_start_date)

        # Key is comes out of db as string, so we add it as a string here
        # so the tracker can compare it properly.
        instance.udf = {str(item['id']): item
                        for item in json_data.get('customFields', list())}

        instance.automatic_email_cc_flag = \
            json_data.get('automaticEmailCcFlag', False)
        instance.automatic_email_contact_flag = \
            json_data.get('automaticEmailContactFlag', False)
        instance.automatic_email_resource_flag = \
            json_data.get('automaticEmailResourceFlag', False)
        instance.automatic_email_cc = \
            json_data.get('automaticEmailCc')
        if instance.automatic_email_cc:
            # Truncate the field to 1000 characters as per CW docs for the
            # automatic_email_cc field, because in some cases more can be
            # received which causes a DataError. It is preferred to keep the
            # DB schema in-line with the CW specifications, even if the
            # specifications are wrong.
            instance.automatic_email_cc = instance.automatic_email_cc[:1000]

        budget_hours = json_data.get('budgetHours')
        actual_hours = json_data.get('actualHours')
        instance.budget_hours = Decimal(str(budget_hours)) \
            if budget_hours is not None else None
        instance.actual_hours = Decimal(str(actual_hours)) \
            if actual_hours is not None else None

        instance.predecessor_type = json_data.get('predecessorType')
        instance.predecessor_closed_flag = \
            json_data.get('predecessorClosedFlag', False)
        instance.lag_days = json_data.get('lagDays')
        instance.lag_non_working_days_flag = \
            json_data.get('lagNonworkingDaysFlag', False)

        instance.contact_name = json_data.get('contactName')
        instance.contact_phone_number = json_data.get('contactPhoneNumber')
        instance.contact_phone_extension = \
            json_data.get('contactPhoneExtension')
        instance.contact_email_address = json_data.get('contactEmailAddress')

        try:
            predecessor_id = json_data.get('predecessorId')

            if predecessor_id:
                if instance.predecessor_type == self.model_class.TICKET:
                    instance.ticket_predecessor = \
                        models.Ticket.objects.get(pk=predecessor_id)
                else:
                    instance.phase_predecessor = \
                        models.ProjectPhase.objects.get(pk=predecessor_id)

        except ObjectDoesNotExist as e:
            logger.warning(
                'Ticket {} has a predecessorId that does not exist. '
                'ObjectDoesNotExist Exception: {}'.format(instance.id, e)
            )

        try:
            merged_parent_id = \
                json_data.get('mergedParentTicket', {}).get('id')

            if merged_parent_id:
                instance.merged_parent = \
                    models.Ticket.objects.get(pk=merged_parent_id)

        except ObjectDoesNotExist as e:
            logger.warning(
                'Ticket {} has a mergedParentTicket that does not exist. '
                'ObjectDoesNotExist Exception: {}'.format(instance.id, e)
            )

        try:
            site_id = json_data.get('site', {}).get('id')

            if site_id:
                instance.company_site = \
                    models.CompanySite.objects.get(pk=site_id)

        except ObjectDoesNotExist as e:
            logger.warning(
                'Ticket {} has a site_id that does not exist. '
                'ObjectDoesNotExist Exception: {}'.format(instance.id, e)
            )

        return instance

    def create(self, fields, **kwargs):
        """
        Send POST request to ConnectWise to create tickets.
        """
        # TODO move to parent synchronizer class when rest of record
        #  creation is in.
        client = self.client_class(
            api_public_key=kwargs.get('api_public_key'),
            api_private_key=kwargs.get('api_private_key')
        )
        # convert the fields to the format that the API expects
        api_fields = self._convert_fields_to_api_format(fields)

        new_record = client.create_ticket(api_fields)

        return self.update_or_create_instance(new_record)

    def delete(self, instance, **kwargs):
        """
        Send DELETE request to ConnectWise to delete ticket.
        """
        client = self.client_class(
            api_public_key=kwargs.get('api_public_key'),
            api_private_key=kwargs.get('api_private_key')
        )
        return client.delete_ticket(instance.id)

    def _convert_fields_to_api_format(self, fields):
        """
        Converts the model field names to the API field names.
        """
        api_fields = {}
        for key, value in fields.items():
            api_fields[self.API_FIELD_NAMES[key]] = value
        return api_fields

    def update(self, record, changed_fields, **kwargs):
        """
        Send PATCH request to ConnectWise to create tickets.
        """
        # TODO move to parent synchronizer class when rest of record
        #  creation is in.
        client = self.client_class(
            api_public_key=kwargs.get('api_public_key'),
            api_private_key=kwargs.get('api_private_key')
        )

        # Handle dependency error: The API throws an error if a ticket has
        # a predecessor. To work around this, we first remove the predecessor,
        # update the required fields, and then re-add the predecessor after
        # the update.
        predecessor_removed = False
        if record.ticket_predecessor and (
            changed_fields.get('estimated_start_date') or
            changed_fields.get('required_date_utc')
        ):
            try:
                predecessor_reset_fields = {
                    'ticket_predecessor': None,
                    'predecessor_type': None,
                    'required_date_utc': None,
                    'estimated_start_date': None
                }
                predecessor_reset_api_fields = \
                    self._convert_fields_to_api_format(
                        predecessor_reset_fields)
                client.update_ticket(record, predecessor_reset_api_fields)
                predecessor_removed = True

                # Set the removed fields for adding back along with predecessor
                changed_fields['ticket_predecessor'] = \
                    record.ticket_predecessor_id
                changed_fields['predecessor_type'] = record.predecessor_type

                if not changed_fields.get('estimated_start_date'):
                    changed_fields['estimated_start_date'] = \
                        record.estimated_start_date

                if not changed_fields.get('required_date_utc'):
                    changed_fields['required_date_utc'] = \
                        record.required_date_utc

            except ConnectWiseAPIError as e:
                error_message = \
                    "Failed to reset predecessor fields for record " + \
                    f"{record.id}"
                logger.error("%s: %s", error_message, str(e))
                error_message = \
                    "The update request failed. " + \
                    "Please refresh the page and try again."
                raise ConnectWiseAPIError(error_message)

        try:
            # convert the fields to the format that the API expects
            api_fields = self._convert_fields_to_api_format(changed_fields)
            updated_record = client.update_ticket(record, api_fields)
        except ConnectWiseAPIError as e:
            error_message = ''

            if predecessor_removed:
                try:
                    rollback_fields = {
                        'ticket_predecessor': record.ticket_predecessor_id,
                        'predecessor_type': record.predecessor_type,
                        'required_date_utc': record.required_date_utc,
                        'estimated_start_date': record.estimated_start_date
                    }

                    # convert the fields to the format that the API expects
                    api_fields = \
                        self._convert_fields_to_api_format(rollback_fields)

                    # Attempt rollback of predecessor and fields
                    client._update_with_retries(record, api_fields)
                except ConnectWiseAPIError as exc:
                    error_message = (
                        "An error occurred while updating " +
                        "record {record.id} and the predecessor, "
                        "Estimated start date, and due date have " +
                        "been removed from the ticket. You must " +
                        "re-add these details manually to the ticket."
                    )
                    logger.error("%s: %s", error_message, str(exc))
                    raise ConnectWiseAPIError(error_message)

            logger.error(str(e))
            raise ConnectWiseAPIError(str(e))

        new_record = self.update_or_create_instance(updated_record)

        return new_record

    def _update_with_retries(self, client, record, api_fields):

        @retry(
            stop_max_attempt_number=client.request_settings['max_attempts'],
            wait_exponential_multiplier=api.RETRY_WAIT_EXPONENTIAL_MULTAPPLIER,
            wait_exponential_max=api.RETRY_WAIT_EXPONENTIAL_MAX,
            retry_on_exception=True
        )
        def _update():
            return client.update_ticket(record, api_fields)

        return _update()


class ServiceTicketSynchronizer(TicketSynchronizerMixin,
                                BatchConditionMixin, Synchronizer):
    client_class = api.ServiceAPIClient
    task_synchronizer_class = ServiceTicketTaskSynchronizer

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request_settings = DjconnectwiseSettings().get_settings()

        sync_child_tickets = request_settings.get('sync_child_tickets')
        if not sync_child_tickets and sync_child_tickets is not None:
            self.api_conditions.append('parentTicketId=null')

    def _assign_field_data(self, instance, json_data):
        instance = super()._assign_field_data(instance, json_data)

        instance.record_type = json_data.get('recordType')
        instance.parent_ticket_id = json_data.get('parentTicketId')
        instance.has_child_ticket = json_data.get('hasChildTicket')

        instance_sla = json_data.get('slaStatus')
        if instance_sla:
            sla_stage, sla_date = parse_sla_status(
                instance_sla,
                instance.entered_date_utc
            )

            instance.sla_stage = sla_stage

            # If resolved or waiting, this will be None
            instance.sla_expire_date = sla_date

        self.set_relations(instance, json_data)
        return instance

    def filter_by_record_type(self):
        return self.model_class.objects.filter(
            record_type=models.Ticket.SERVICE_TICKET)

    def merge_ticket(self, merge_data, **kwargs):
        """
        Send POST request to ConnectWise to merge tickets.
        """
        service_client = api.ServiceAPIClient(
            api_public_key=kwargs.get('api_public_key'),
            api_private_key=kwargs.get('api_private_key')
        )
        return service_client.post_merge_ticket(merge_data, **kwargs)


class ProjectTicketSynchronizer(TicketSynchronizerMixin,
                                BatchConditionMixin, Synchronizer):
    client_class = api.ProjectAPIClient
    task_synchronizer_class = ProjectTicketTaskSynchronizer

    def _assign_field_data(self, instance, json_data):
        instance = super()._assign_field_data(instance, json_data)

        instance.wbs_code = json_data.get('wbsCode')
        # Tickets from the project/tickets API endpoint do not include the
        # record type field but we use the same Ticket model for project and
        # service tickets so we need to set the record type here.
        if json_data.get('isIssueFlag'):
            # TODO update app to work with project issue flag instead of
            #  legacy record_type field.
            instance.record_type = models.Ticket.PROJECT_ISSUE
            instance.is_issue_flag = True
        else:
            instance.record_type = models.Ticket.PROJECT_TICKET

        self.set_relations(instance, json_data)
        return instance

    def filter_by_record_type(self):
        project_record_types = [
            models.Ticket.PROJECT_ISSUE, models.Ticket.PROJECT_TICKET
        ]
        return self.model_class.objects.filter(
            record_type__in=project_record_types)


class CalendarSynchronizer(Synchronizer):
    client_class = api.ScheduleAPIClient
    model_class = models.CalendarTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        instance.monday_start_time = \
            parse(json_data.get('mondayStartTime')).time() \
            if json_data.get('mondayStartTime') else None
        instance.monday_end_time = \
            parse(json_data.get('mondayEndTime')).time() \
            if json_data.get('mondayEndTime') else None
        instance.tuesday_start_time = \
            parse(json_data.get('tuesdayStartTime')).time() \
            if json_data.get('tuesdayStartTime') else None
        instance.tuesday_end_time = \
            parse(json_data.get('tuesdayEndTime')).time() \
            if json_data.get('tuesdayEndTime') else None
        instance.wednesday_start_time = \
            parse(json_data.get('wednesdayStartTime')).time() \
            if json_data.get('wednesdayStartTime') else None
        instance.wednesday_end_time = \
            parse(json_data.get('wednesdayEndTime')).time() \
            if json_data.get('wednesdayEndTime') else None
        instance.thursday_start_time = \
            parse(json_data.get('thursdayStartTime')).time() \
            if json_data.get('thursdayStartTime') else None
        instance.thursday_end_time = \
            parse(json_data.get('thursdayEndTime')).time() \
            if json_data.get('thursdayEndTime') else None
        instance.friday_start_time = \
            parse(json_data.get('fridayStartTime')).time() \
            if json_data.get('fridayStartTime') else None
        instance.friday_end_time = \
            parse(json_data.get('fridayEndTime')).time() \
            if json_data.get('fridayEndTime') else None
        instance.saturday_start_time = \
            parse(json_data.get('saturdayStartTime')).time() \
            if json_data.get('saturdayStartTime') else None
        instance.saturday_end_time = \
            parse(json_data.get('saturdayEndTime')).time() \
            if json_data.get('saturdayEndTime') else None
        instance.sunday_start_time = \
            parse(json_data.get('sundayStartTime')).time() \
            if json_data.get('sundayStartTime') else None
        instance.sunday_end_time = \
            parse(json_data.get('sundayEndTime')).time() \
            if json_data.get('sundayEndTime') else None

        self._assign_relation(
            instance,
            json_data,
            'holidayList',
            models.HolidayList,
            'holiday_list'
            )

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_calendars(*args, **kwargs)


class HolidaySynchronizer(ChildFetchRecordsMixin, Synchronizer):
    client_class = api.ScheduleAPIClient
    model_class = models.HolidayTracker
    parent_model_class = models.HolidayList

    def _assign_field_data(self, instance, json_data):

        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        instance.all_day_flag = json_data.get('allDayFlag')
        instance.date = parse(json_data.get('date')).date()
        instance.start_time = \
            parse(json_data.get('timeStart')).time() \
            if json_data.get('timeStart') else None
        instance.end_time = \
            parse(json_data.get('timeEnd')).time() \
            if json_data.get('timeEnd') else None

        self._assign_relation(
            instance,
            json_data,
            'holidayList',
            models.HolidayList,
            'holiday_list'
            )

        return instance

    def client_call(self, list_id, *args, **kwargs):
        return self.client.get_holidays(list_id, *args, **kwargs)


class HolidayListSynchronizer(Synchronizer):
    client_class = api.ScheduleAPIClient
    model_class = models.HolidayListTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_holiday_lists(*args, **kwargs)


class OpportunitySynchronizer(UpdateRecordMixin, Synchronizer):
    client_class = api.SalesAPIClient
    model_class = models.OpportunityTracker
    related_meta = {
        'type': (models.OpportunityType, 'opportunity_type'),
        'stage': (models.OpportunityStage, 'stage'),
        'status': (models.OpportunityStatus, 'status'),
        'probability': (models.SalesProbability, 'probability'),
        'primarySalesRep': (models.Member, 'primary_sales_rep'),
        'secondarySalesRep': (models.Member, 'secondary_sales_rep'),
        'company': (models.Company, 'company'),
        'contact': (models.Contact, 'contact'),
        'closedBy': (models.Member, 'closed_by')
    }

    API_FIELD_NAMES = {
        'name': 'name',
        'stage': 'stage',
        'notes': 'notes',
        'contact': 'contact',
        'expected_close_date': 'expectedCloseDate',
        'opportunity_type': 'type',
        'status': 'status',
        'source': 'source',
        'primary_sales_rep': 'primarySalesRep',
        'secondary_sales_rep': 'secondarySalesRep',
        'location_id': 'locationId',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # only synchronize Opportunities that do not have an OpportunityStatus
        # with the closedFlag=True
        open_statuses = list(
            models.OpportunityStatus.objects.
            filter(closed_flag=False).
            order_by(self.lookup_key).
            values_list('id', flat=True)
        )
        if open_statuses:
            # Only do this if we know of at least one open status.
            self.api_conditions.append(
                'status/id in ({})'.format(
                    ','.join([str(i) for i in open_statuses])
                )
            )

    def _update_or_create_child(self, model_class, json_data):
        child_name = json_data['name']
        # Setting the name default ensures that if Django has to create the
        # object, then the name has already been set and we don't have to save
        # again.
        child, created = model_class.objects.get_or_create(
            id=json_data['id'],
            defaults={
                'name': child_name,
            }
        )
        if not created:
            # Ensure the name is up to date.
            child.name = child_name

            # Don't save it if there was no change
            if child.tracker.changed():
                child.save()
        return child

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        notes = json_data.get('notes')
        if notes:
            instance.notes = normalize_newlines(notes)
        instance.source = json_data.get('source')
        instance.location_id = json_data.get('locationId')
        instance.business_unit_id = json_data.get('businessUnitId')
        instance.customer_po = json_data.get('customerPO')
        instance.udf = {str(item['id']): item
                        for item in json_data.get('customFields', list())}

        # handle dates
        expected_close_date = json_data.get('expectedCloseDate')
        if expected_close_date:
            instance.expected_close_date = parse(expected_close_date).date()

        pipeline_change_date = json_data.get('pipelineChangeDate')
        if pipeline_change_date:
            instance.pipeline_change_date = parse(pipeline_change_date)

        date_became_lead = json_data.get('dateBecameLead')
        if date_became_lead:
            instance.date_became_lead = parse(date_became_lead)

        closed_date = json_data.get('closedDate')
        if closed_date:
            instance.closed_date = parse(closed_date)

        priority = json_data.get('priority')
        if priority:
            instance.priority = self._update_or_create_child(
                models.OpportunityPriorityTracker, priority
            )

        self.set_relations(instance, json_data)
        return instance

    def update_record(self, client, record, api_fields):
        return client.update_opportunity(record, api_fields)

    def get_page(self, *args, **kwargs):
        return self.client.get_opportunities(*args, **kwargs)

    def get_single(self, opportunity_id):
        return self.client.by_id(opportunity_id)


class OpportunityStageSynchronizer(Synchronizer):
    client_class = api.SalesAPIClient
    model_class = models.OpportunityStageTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_opportunity_stages(*args, **kwargs)


class OpportunityStatusSynchronizer(Synchronizer):
    client_class = api.SalesAPIClient
    model_class = models.OpportunityStatusTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        instance.won_flag = json_data['wonFlag']
        instance.lost_flag = json_data['lostFlag']
        instance.closed_flag = json_data['closedFlag']
        instance.inactive_flag = json_data['inactiveFlag']
        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_opportunity_statuses(*args, **kwargs)


class OpportunityTypeSynchronizer(Synchronizer):
    client_class = api.SalesAPIClient
    model_class = models.OpportunityTypeTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.description = json_data.get('description')
        instance.inactive_flag = json_data.get('inactiveFlag')
        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_opportunity_types(*args, **kwargs)


class TypeSynchronizer(BoardFilterMixin, Synchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.TypeTracker

    related_meta = {
        'board': (models.ConnectWiseBoard, 'board')
    }

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        instance.inactive_flag = json_data.get('inactiveFlag')

        self.set_relations(instance, json_data)
        return instance

    def client_call(self, board_id, *args, **kwargs):
        return self.client.get_types(board_id, *args, **kwargs)


class SubTypeSynchronizer(BoardFilterMixin, Synchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.SubTypeTracker

    related_meta = {
        'board': (models.ConnectWiseBoard, 'board')
    }

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        instance.inactive_flag = json_data.get('inactiveFlag')

        self.set_relations(instance, json_data)
        return instance

    def client_call(self, board_id, *args, **kwargs):
        return self.client.get_subtypes(board_id, *args, **kwargs)


class ItemSynchronizer(BoardFilterMixin, Synchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.ItemTracker

    related_meta = {
        'board': (models.ConnectWiseBoard, 'board')
    }

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        instance.inactive_flag = json_data.get('inactiveFlag')

        self.set_relations(instance, json_data)
        return instance

    def client_call(self, board_id, *args, **kwargs):
        return self.client.get_items(board_id, *args, **kwargs)


class TypeSubTypeItemAssociationSynchronizer(BoardFilterMixin, Synchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.TypeSubTypeItemAssociationTracker

    related_meta = {
        'type': (models.Type, 'type'),
        'subType': (models.SubType, 'sub_type'),
        'item': (models.Item, 'item'),
        'board': (models.ConnectWiseBoard, 'board')
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # This endpoint does not have a lastUpdated field available.
        # So we cannot use the regular partial sync pattern.
        self.partial_sync_support = False

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')

        self.set_relations(instance, json_data)

    def client_call(self, board_id, *args, **kwargs):
        return self.client.get_type_subtype_item_associations(
            board_id, *args, **kwargs)


class WorkTypeSynchronizer(Synchronizer):
    client_class = api.TimeAPIClient
    model_class = models.WorkTypeTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        instance.inactive_flag = json_data.get('inactiveFlag')
        instance.overall_default_flag = json_data.get('overallDefaultFlag')
        if json_data.get('billTime') == 'NoDefault':
            instance.bill_time = None
        else:
            instance.bill_time = json_data.get('billTime')

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_work_types(*args, **kwargs)


class WorkRoleSynchronizer(Synchronizer):
    client_class = api.TimeAPIClient
    model_class = models.WorkRoleTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        instance.inactive_flag = json_data.get('inactiveFlag')

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_work_roles(*args, **kwargs)


class ProjectRoleSynchronizer(Synchronizer):
    client_class = api.ProjectAPIClient
    model_class = models.ProjectRoleTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        instance.manager_role_flag = json_data.get('managerRoleFlag')
        instance.default_contact_flag = json_data.get('defaultContactFlag')

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_project_roles(*args, **kwargs)


class AgreementSynchronizer(Synchronizer):
    client_class = api.FinanceAPIClient
    model_class = models.AgreementTracker

    related_meta = {
        'workRole': (models.WorkRole, 'work_role'),
        'workType': (models.WorkType, 'work_type'),
        'company': (models.Company, 'company')
    }

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        instance.agreement_status = json_data.get('agreementStatus')
        instance.cancelled_flag = json_data.get('cancelledFlag')

        if json_data.get('type'):
            instance.agreement_type = json_data['type'].get('name')

        if json_data.get('billTime') == 'NoDefault':
            instance.bill_time = None
        else:
            instance.bill_time = json_data.get('billTime')

        self.set_relations(instance, json_data)
        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_agreements(*args, **kwargs)


class SourceSynchronizer(Synchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.SourceTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.name = json_data.get('name')
        instance.default_flag = json_data.get('defaultFlag')

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_sources(*args, **kwargs)


class UDFSynchronizer(Synchronizer):

    def fetch_records(self, results, conditions=None):
        """
        Only fetch one record. To ensure we get a record if one exists, just
        make a call for tickets but only ask for 1 pages, with a page size of 1
        """
        page = 1
        logger.info('Fetching {} records'.format(
            self.model_class.__bases__[0].__name__))
        page_records = self.get_page(
            page=page,
            page_size=page,
        )
        for record in page_records:
            # Should only run once, or not at all if there are 0 records of
            # requested type.
            self.persist_page(record.get('customFields', list()), results)

        return results

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data.get('id')
        instance.caption = json_data.get('caption')
        instance.type = json_data.get('type')
        instance.entry_method = json_data.get('entryMethod')
        instance.number_of_decimals = json_data.get('numberOfDecimals')

        return instance


class TicketUDFSynchronizer(UDFSynchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.TicketUDFTracker

    def get_page(self, *args, **kwargs):
        # Using the Service API Client fine for both service and project
        #   tickets as both ticket types have all UDFs returned in a request
        return self.client.get_tickets(*args, **kwargs)


class ProjectUDFSynchronizer(UDFSynchronizer):
    client_class = api.ProjectAPIClient
    model_class = models.ProjectUDFTracker

    def get_page(self, *args, **kwargs):
        return self.client.get_projects(*args, **kwargs)


class ActivityUDFSynchronizer(UDFSynchronizer):
    client_class = api.SalesAPIClient
    model_class = models.ActivityUDFTracker

    def get_page(self, *args, **kwargs):
        return self.client.get_activities(*args, **kwargs)


class OpportunityUDFSynchronizer(UDFSynchronizer):
    client_class = api.SalesAPIClient
    model_class = models.OpportunityUDFTracker

    def get_page(self, *args, **kwargs):
        return self.client.get_opportunities(*args, **kwargs)
