import logging
import datetime
import math


from dateutil.parser import parse
from copy import deepcopy
from decimal import Decimal

from django.core.files.storage import default_storage
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.db.models import Q

from djconnectwise import api
from djconnectwise import models
from djconnectwise.utils import get_hash, get_filename_extension, \
    generate_thumbnail, generate_filename, remove_thumbnail
from djconnectwise.utils import DjconnectwiseSettings

from botocore.exceptions import NoCredentialsError

DEFAULT_AVATAR_EXTENSION = 'jpg'
MAX_URL_LENGTH = 2000
MIN_URL_LENGTH = 1980

CREATED = 1
UPDATED = 2
SKIPPED = 3

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
            except InvalidObjectException as e:
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
            elif instance.tracker.changed():
                instance.save()
                result = UPDATED
            else:
                result = SKIPPED
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
            delete_qset.delete()
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
            last_sync_job_time = sync_job_qset.exclude(
                id=sync_job_qset.last().id).last().start_time.isoformat()
            self.api_conditions.append(
                "lastUpdated>[{0}]".format(last_sync_job_time)
            )
        results = SyncResults()
        results = self.get(results, )

        if self.full:
            # Set of IDs of all records prior to sync,
            # to find stale records for deletion.
            initial_ids = self._instance_ids()

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
                ' Updated: {}, Skipped: {},Deleted: {}'.format(
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
            optimal_size = self.get_optimal_size(unfetched_conditions)
            batch_conditions = unfetched_conditions[:optimal_size]
            del unfetched_conditions[:optimal_size]
            batch_condition = self.get_batch_condition(batch_conditions)
            batch_conditions = deepcopy(self.api_conditions)
            batch_conditions.append(batch_condition)
            results = super().get(results, conditions=batch_conditions)
        return results

    def get_optimal_size(self, condition_list):
        if not condition_list:
            # Return none if empty list
            return None
        size = len(condition_list)
        if self.url_length(condition_list, size) < MAX_URL_LENGTH:
            # If we can fit all of the statuses in the first batch, return
            return size

        max_size = size
        min_size = 1
        while True:
            url_len = self.url_length(condition_list, size)
            if url_len <= MAX_URL_LENGTH and url_len > MIN_URL_LENGTH:
                break
            elif url_len > MAX_URL_LENGTH:
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
        # don't undercut it (300), and add size, because for the amount of
        # conditions, there will be just as many commas separating them
        return sum(len(str(i)) for i in condition_list[:size]) + 300 + size


class CallbackPartialSyncMixin:
    """
    Run a partial sync on callbacks for related synchronizers. If a ticket
    has many notes or time entries they could all be fetched
    when a callback runs. This could mean a lot of time and resources spent
    syncing old notes or time entries. We will continue to return
    deleted_count even though it will always be zero in this case.
    """
    def callback_sync(self, filter_params):
        sync_job_qset = self.get_sync_job_qset()

        if sync_job_qset.exists():
            last_sync_job_time = sync_job_qset.last().start_time.isoformat()
            self.api_conditions.append(
                "lastUpdated>[{0}]".format(last_sync_job_time)
            )

        results = SyncResults()
        results = self.get(results, )

        return results.created_count, results.updated_count, \
            results.skipped_count, results.deleted_count


class ServiceNoteSynchronizer(CallbackPartialSyncMixin, Synchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.ServiceNoteTracker

    related_meta = {
        'member': (models.Member, 'member')
    }

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.text = json_data.get('text')
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
            ticket_id = json_data['ticketId']
            related_ticket = ticket_class.objects.get(pk=ticket_id)
            setattr(instance, 'ticket', related_ticket)
        except KeyError:
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

    def get_page(self, *args, **kwargs):
        records = []
        ticket_qs = models.Ticket.objects.all().order_by(self.lookup_key)

        # We are using the conditions here to specify getting a single
        # tickets notes. If conditions are supplied, like when a ticket
        # callback is fired, then replace the conditions with the
        # last updated sync time instead of syncing all notes all the time.
        conditions = kwargs.get('conditions')
        if conditions:
            try:
                ticket_id = int(conditions[0])
                kwargs['conditions'] = \
                    [conditions[1]] if len(conditions) > 1 else []

                records += self.client_call(ticket_id, *args, **kwargs)
                return records
            except ValueError:
                # Do nothing
                pass
        for ticket_id in ticket_qs.values_list('id', flat=True):
            records += self.client_call(ticket_id, *args, **kwargs)

        return records

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
        self.client = self.client_class()
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
        'task': 'notes'
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
            self.sync_tasks(ticket)

    def sync_tasks(self, instance):
        tasks = self.get(parent=instance.id)
        instance.tasks_total = len(tasks)
        instance.tasks_completed = sum(task['closed_flag'] for task in tasks)

        instance.save()


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


class OpportunityNoteSynchronizer(Synchronizer):
    client_class = api.SalesAPIClient
    model_class = models.OpportunityNoteTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
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

    def get_page(self, *args, **kwargs):
        records = []
        opportunity_qs = models.Opportunity.objects.all()\
            .order_by(self.lookup_key)

        for opportunity_id in opportunity_qs.values_list('id', flat=True):
            records += self.client_call(opportunity_id, *args, **kwargs)

        return records


class BoardSynchronizer(Synchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.ConnectWiseBoardTracker

    related_meta = {
        'workRole': (models.WorkRole, 'work_role'),
        'workType': (models.WorkType, 'work_type')
    }

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']
        if json_data['billTime'] == 'NoDefault':
            instance.bill_time = None
        else:
            instance.bill_time = json_data['billTime']

        if 'inactiveFlag' in json_data:
            # This is the new CW way
            instance.inactive = json_data.get('inactiveFlag')
        else:
            # This is old, but keep for backwards-compatibility
            instance.inactive = json_data.get('inactive')

        instance.project_flag = json_data.get('projectFlag', False)

        self.set_relations(instance, json_data)
        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_boards(*args, **kwargs)


class BoardChildSynchronizer(Synchronizer):

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']
        try:
            board_id = json_data['board']['id']
        except KeyError:
            # Must be 2017.5 or earlier
            board_id = json_data['boardId']
        instance.board = models.ConnectWiseBoard.objects.get(id=board_id)
        return instance

    def client_call(self, board_id):
        raise NotImplementedError


class BoardStatusSynchronizer(BoardChildSynchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.BoardStatusTracker

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
        kwargs['conditions'] = self.api_conditions
        return self.client.get_statuses(board_id, *args, **kwargs)

    def get_page(self, *args, **kwargs):
        records = []
        board_qs = models.ConnectWiseBoard.objects.all()\
            .order_by(self.lookup_key)

        for board_id in board_qs.values_list('id', flat=True):
            records += self.client_call(board_id, *args, **kwargs)

        return records


class BoardFilterMixin:

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request_settings = DjconnectwiseSettings().get_settings()
        board_names = request_settings.get('board_status_filter')
        self.boards = [board.strip() for board in board_names.split(',')] \
            if board_names else None

    def get_page(self, *args, **kwargs):
        records = []
        if self.boards:
            board_qs = models.ConnectWiseBoard.available_objects.filter(
                name__in=self.boards).order_by(self.lookup_key)
        else:
            board_qs = models.ConnectWiseBoard.available_objects.all().\
                order_by(self.lookup_key)

        for board_id in board_qs.values_list('id', flat=True):
            records += self.client_call(board_id, *args, **kwargs)

        return records


class TeamSynchronizer(BoardFilterMixin, BoardChildSynchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.TeamTracker

    def _assign_field_data(self, instance, json_data):
        instance = super(TeamSynchronizer, self)._assign_field_data(
            instance, json_data)

        members = []
        if json_data.get('members'):
            members = list(models.Member.objects.filter(
                id__in=json_data['members']))

        instance.save()

        instance.members.clear()
        instance.members.add(*members)
        return instance

    def client_call(self, board_id, *args, **kwargs):
        return self.client.get_teams(board_id, *args, **kwargs)


class CompanySynchronizer(Synchronizer):
    client_class = api.CompanyAPIClient
    model_class = models.CompanyTracker

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_conditions = ['deletedFlag=False']

    def _assign_field_data(self, company, company_json):
        """
        Assigns field data from an company_json instance
        to a local Company model instance
        """
        company.id = company_json['id']
        company.name = company_json['name']
        company.identifier = company_json['identifier']

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

        types_list = company_json.get('typeIds', [])
        for type_id in types_list:
            try:
                company_type = models.CompanyType.objects.get(
                    pk=type_id)
                company.company_types.add(company_type)
            except models.CompanyType.DoesNotExist:
                logger.warning(
                    'Failed to find CompanyType: {}'.format(
                        type_id
                    )
                )

        territory_id = company_json.get('territoryId')
        if territory_id:
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
                'No Territory ID recieved in request for Company: {}'.format(
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
        instance.id = json_data['id']
        instance.name = json_data['name']
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
            instance.track_id = json_data['track']['id']

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_company_statuses(*args, **kwargs)


class CompanyTypeSynchronizer(Synchronizer):
    client_class = api.CompanyAPIClient
    model_class = models.CompanyTypeTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data.get('name')
        instance.vendor_flag = json_data['vendorFlag']

    def get_page(self, *args, **kwargs):
        return self.client.get_company_types(*args, **kwargs)


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
        instance.id = json_data['id']
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

        contact_communication_sync = ContactCommunicationSynchronizer()
        contact_communication_sync.api_conditions = [instance_id]
        sync_classes.append((contact_communication_sync,
                             Q(contact=instance_id)))
        self.sync_children(*sync_classes)


class ContactCommunicationSynchronizer(Synchronizer):
    client_class = api.CompanyAPIClient
    model_class = models.ContactCommunicationTracker

    related_meta = {
        'type': (models.CommunicationType, 'type'),
    }

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
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

    def get_page(self, *args, **kwargs):
        records = []
        conditions = kwargs.get('conditions')
        if conditions:
            try:
                contact_id = int(conditions[0])
                kwargs['conditions'] = [conditions[1]] if len(
                    conditions) > 1 else []

                records += self.client_call(contact_id, *args, **kwargs)
                return records
            except ValueError:
                # Do nothing
                pass

        contact_qs = models.Contact.objects.all()
        for contact_id in contact_qs.values_list('id', flat=True):
            records += self.client_call(contact_id, *args, **kwargs)

        return records

    def get_single(self, communication_id):
        return self.client.get_single_communication(communication_id)


class CommunicationTypeSynchronizer(Synchronizer):
    client_class = api.CompanyAPIClient
    model_class = models.CommunicationTypeTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
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
        instance.id = json_data['id']
        self.set_relations(instance, json_data)
        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_mycompanyother(*args, **kwargs)


class ActivityStatusSynchronizer(Synchronizer):
    client_class = api.SalesAPIClient
    model_class = models.ActivityStatusTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']
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
        instance.id = json_data['id']
        instance.name = json_data['name']
        instance.points = json_data['points']
        instance.default_flag = json_data.get('defaultFlag', False)
        instance.inactive_flag = json_data.get('inactiveFlag', False)
        instance.email_flag = json_data.get('emailFlag', False)
        instance.memo_flag = json_data.get('memoFlag', False)
        instance.history_flag = json_data.get('historyFlag', False)

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_activity_types(*args, **kwargs)


class ActivitySynchronizer(Synchronizer):
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
        instance.id = json_data['id']
        instance.name = json_data['name']
        instance.notes = json_data.get('notes')

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

    def get_page(self, *args, **kwargs):
        return self.client.get_activities(*args, **kwargs)

    def get_single(self, activity_id):
        return self.client.get_single_activity(activity_id)


class SalesProbabilitySynchronizer(Synchronizer):
    client_class = api.SalesAPIClient
    model_class = models.SalesProbabilityTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.probability = json_data['probability']

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
            "(type/identifier='S' or type/identifier='O')"
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
            self.batch_condition_list = list(ticket_ids | opportunity_ids)

    def get(self, results, conditions=None):

        if self.no_batch:
            self.fetch_records(results, conditions)
        else:
            super().get(results, conditions)

        return results

    def get_optimal_size(self, condition_list):
        object_id_size = self.settings['schedule_entry_conditions_size']

        return object_id_size if object_id_size \
            else super().get_optimal_size(condition_list)

    def get_batch_condition(self, conditions):
        return 'objectId in ({})'.format(
            ','.join([str(i) for i in conditions])
        )

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
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
            member_id = json_data['member']['id']
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
            uid = json_data['objectId']
        except KeyError:
            raise InvalidObjectException(
                'Schedule entry {} has no objectId key to find its target'
                '- skipping.'.format(instance.id)
            )

        if json_data['type']['identifier'] == "S":
            try:
                related_ticket = ticket_class.objects.get(pk=uid)
                if json_data['doneFlag']:
                    setattr(instance, 'ticket_object', None)
                else:
                    setattr(instance, 'ticket_object', related_ticket)
            except ObjectDoesNotExist as e:
                logger.warning(
                    'Ticket not found for {}.'.format(instance.id) +
                    ' ObjectDoesNotExist Exception: {}.'.format(e)
                )
        elif json_data['type']['identifier'] == "C":
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
        instance.id = json_data['id']
        instance.name = json_data['name']

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_schedule_statuses(*args, **kwargs)


class ScheduleTypeSynchronizer(Synchronizer):
    client_class = api.ScheduleAPIClient
    model_class = models.ScheduleTypeTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']
        instance.identifier = json_data['identifier']

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_schedule_types(*args, **kwargs)


class TerritorySynchronizer(Synchronizer):
    client_class = api.SystemAPIClient
    model_class = models.TerritoryTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_territories(*args, **kwargs)


class TimeEntrySynchronizer(BatchConditionMixin,
                            CallbackPartialSyncMixin, Synchronizer):
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
        instance.id = json_data['id']
        instance.charge_to_type = json_data['chargeToType']
        instance.billable_option = json_data.get('billableOption')
        instance.notes = json_data.get('notes')
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
        location.id = location_json['id']
        location.name = location_json['name']
        location.where = location_json.get('where')
        return location

    def get_page(self, *args, **kwargs):
        return self.client.get_locations(*args, **kwargs)


class PrioritySynchronizer(Synchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.TicketPriorityTracker

    def _assign_field_data(self, ticket_priority, api_priority):
        ticket_priority.id = api_priority['id']
        ticket_priority.name = api_priority['name']
        ticket_priority.color = api_priority.get('color')

        # work around due to api data inconsistencies
        sort_value = api_priority.get('sort') or api_priority.get('sortOrder')
        if sort_value:
            ticket_priority.sort = sort_value

        return ticket_priority

    def get_page(self, *args, **kwargs):
        return self.client.get_priorities(*args, **kwargs)


class ProjectStatusSynchronizer(Synchronizer):

    client_class = api.ProjectAPIClient
    model_class = models.ProjectStatusTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']
        instance.default_flag = json_data.get('defaultFlag')
        instance.inactive_flag = json_data.get('inactiveFlag')
        instance.closed_flag = json_data.get('closedFlag')
        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_project_statuses(*args, **kwargs)


class ProjectPhaseSynchronizer(Synchronizer):
    client_class = api.ProjectAPIClient
    model_class = models.ProjectPhaseTracker
    related_meta = {
        'board': (models.ConnectWiseBoard, 'board')
    }

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.description = json_data['description']
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

        if json_data['billTime'] == 'NoDefault':
            instance.bill_time = None
        else:
            instance.bill_time = json_data['billTime']

        scheduled_start = json_data.get('scheduledStart')
        scheduled_end = json_data.get('scheduledEnd')
        actual_start = json_data.get('actualStart')
        actual_end = json_data.get('actualEnd')

        if scheduled_start:
            instance.scheduled_start = parse(scheduled_start).date()

        if scheduled_end:
            instance.scheduled_end = parse(scheduled_end).date()

        if actual_start:
            instance.actual_start = parse(actual_start).date()

        if actual_end:
            instance.actual_end = parse(actual_end).date()

        try:
            project_id = json_data['projectId']
            related_project = models.Project.objects.get(pk=project_id)
            setattr(instance, 'project', related_project)
        except KeyError:
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

    def get_page(self, *args, **kwargs):
        records = []
        project_qs = models.Project.objects.all().order_by(self.lookup_key)

        for project_id in project_qs.values_list('id', flat=True):
            records += self.client_call(project_id, *args, **kwargs)

        return records


class ProjectTypeSynchronizer(Synchronizer):
    client_class = api.ProjectAPIClient
    model_class = models.ProjectTypeTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']
        instance.default_flag = json_data.get('defaultFlag')
        instance.inactive_flag = json_data.get('inactiveFlag')
        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_project_types(*args, **kwargs)


class ProjectTeamMemberSynchronizer(Synchronizer):
    client_class = api.ProjectAPIClient
    model_class = models.ProjectTeamMemberTracker

    related_meta = {
        'member': (models.Member, 'member'),
        'workRole': (models.WorkRole, 'work_role')
    }

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        start_date = json_data.get('startDate')
        end_date = json_data.get('endDate')

        if start_date:
            instance.start_date = parse(start_date)
        if end_date:
            instance.end_date = parse(end_date)

        try:
            project_id = json_data['projectId']
            related_project = models.Project.objects.get(pk=project_id)
            setattr(instance, 'project', related_project)
        except KeyError:
            raise InvalidObjectException(
                'Project team member {} has no projectId key to find its '
                'target - skipping.'.format(instance.id)
            )
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

    def get_page(self, *args, **kwargs):
        records = []
        project_qs = models.Project.objects.filter(
            status__closed_flag=False).order_by(self.lookup_key)

        for project_id in project_qs.values_list('id', flat=True):
            records += self.client_call(project_id, *args, **kwargs)

        return records


class ProjectSynchronizer(Synchronizer):
    client_class = api.ProjectAPIClient
    model_class = models.ProjectTracker
    related_meta = {
        'status': (models.ProjectStatus, 'status'),
        'manager': (models.Member, 'manager'),
        'company': (models.Company, 'company'),
        'contact': (models.Contact, 'contact'),
        'type': (models.ProjectType, 'type'),
        'board': (models.ConnectWiseBoard, 'board'),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.full:
            # Only sync projects in non-closed statuses. We could simply use
            # closedFlag=False but API versions before 2019.5 don't support the
            # closedFlag field and we need to support those versions for now.
            self.api_conditions = ['status/id in ({})'.format(
                ','.join(
                    str(i.id) for
                    i in models.ProjectStatus.objects.filter(closed_flag=False)
                )
            )]

    def _assign_field_data(self, instance, json_data):
        actual_start = json_data.get('actualStart')
        actual_end = json_data.get('actualEnd')
        estimated_start = json_data.get('estimatedStart')
        estimated_end = json_data.get('estimatedEnd')
        scheduled_start = json_data.get('scheduledStart')
        scheduled_end = json_data.get('scheduledEnd')

        instance.id = json_data['id']
        instance.name = json_data['name']
        instance.description = json_data.get('description')
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

    def get_page(self, *args, **kwargs):
        return self.client.get_projects(*args, **kwargs)

    def get_single(self, project_id):
        return self.client.get_project(project_id)


class MemberSynchronizer(Synchronizer):
    client_class = api.SystemAPIClient
    model_class = models.MemberTracker

    related_meta = {
        'workRole': (models.WorkRole, 'work_role'),
        'workType': (models.WorkType, 'work_type')
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_sync_job_time = None

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.first_name = json_data.get('firstName')
        instance.last_name = json_data.get('lastName')
        instance.identifier = json_data.get('identifier')
        instance.office_email = json_data.get('officeEmail')
        instance.license_class = json_data.get('licenseClass')
        instance.inactive = json_data.get('inactiveFlag')

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
                except Exception as e:
                    logger.warning("Error saving member avatar. {}".format(e))

                # Just delete the currently saved avatar image
                # so we don't need to worry about cleaning up
                # duplicates or old thumbnails
                if avatar_file and filename:
                    default_storage.delete(current_filename)

                    logger.info("Saving member '{}' avatar to {}.".format(
                        member.identifier, filename))
                    default_storage.save(filename, avatar_file)
                else:
                    # If there were any problems saving the avatar clear the
                    # filename from the member
                    member.avatar = ""

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
        'sla': (models.Sla, 'sla'),
        'type': (models.Type, 'type'),
        'subType': (models.SubType, 'sub_type'),
        'item': (models.Item, 'sub_type_item'),
        'agreement': (models.Agreement, 'agreement'),
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
        board_names = request_settings.get('board_status_filter')
        filtered_statuses = models.BoardStatus.available_objects.filter(
            closed_status=False).order_by(self.lookup_key)

        if board_names:
            boards = [board.strip() for board in board_names.split(',')]

            boards_exist = models.ConnectWiseBoard.available_objects.filter(
                name__in=boards).exists()

            if boards_exist:
                filtered_statuses = filtered_statuses.filter(
                    board__name__in=boards
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

        # lastUpdated is only present when running full syncs.
        if not self.full:
            last_updated = self.api_conditions[-1]
            condition = '{} and {}'.format(condition, last_updated)

        batch_condition = '{} or {}'.format(batch_condition, condition)
        return batch_condition

    def get_page(self, *args, **kwargs):
        return self.client.get_tickets(*args, **kwargs)

    def get_single(self, ticket_id):
        return self.client.get_ticket(ticket_id)

    # sync_config is read-only, so mutable argument is used for simplicity.
    def sync_related(self, instance, sync_config={}):
        instance_id = instance.id
        sync_classes = []

        if sync_config.get('sync_service_note', True):
            note_sync = ServiceNoteSynchronizer()
            note_sync.api_conditions = [instance_id]
            sync_classes.append((note_sync, Q(ticket=instance)))

        if sync_config.get('sync_time_entry', True):
            time_sync = TimeEntrySynchronizer()
            time_sync.batch_condition_list = [instance_id]
            sync_classes.append((time_sync, Q(charge_to_id=instance)))

        if sync_config.get('sync_activity', True):
            activity_sync = ActivitySynchronizer()
            activity_sync.api_conditions = ['ticket/id={}'.format(instance_id)]
            sync_classes.append((activity_sync, Q(ticket=instance)))

        self.task_synchronizer_class().sync_tasks(instance)

        self.sync_children(*sync_classes)

    def fetch_sync_by_id(self, instance_id, sync_config={}):
        instance = super().fetch_sync_by_id(instance_id)
        if not instance.closed_flag:
            self.sync_related(instance, sync_config)
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

        instance.id = json_data['id']
        instance.summary = json_data['summary']
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
            # available for SLA calculation.
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

        instance.lag_days = json_data.get('lagDays')
        instance.lag_non_working_days_flag = \
            json_data.get('lagNonworkingDaysFlag', False)

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

        return instance


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
        instance.respond_mins = json_data.get('respondMinutes')
        instance.res_plan_mins = json_data.get('resPlanMinutes')
        instance.resolve_mins = json_data.get('resolveMinutes')
        instance.date_resolved_utc = json_data.get('dateResolved')
        instance.date_resplan_utc = json_data.get('dateResplan')
        instance.date_responded_utc = json_data.get('dateResponded')

        if instance.date_resolved_utc:
            instance.date_resolved_utc = parse(instance.date_resolved_utc)
        if instance.date_resplan_utc:
            instance.date_resplan_utc = parse(instance.date_resplan_utc)
        if instance.date_responded_utc:
            instance.date_responded_utc = parse(instance.date_responded_utc)

        self.set_relations(instance, json_data)
        return instance

    def filter_by_record_type(self):
        return self.model_class.objects.filter(
            record_type=models.Ticket.SERVICE_TICKET)


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
            instance.record_type = models.Ticket.PROJECT_ISSUE
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
        instance.id = json_data['id']
        instance.name = json_data['name']
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


class HolidaySynchronizer(Synchronizer):
    client_class = api.ScheduleAPIClient
    model_class = models.HolidayTracker

    def _assign_field_data(self, instance, json_data):

        instance.id = json_data['id']
        instance.name = json_data['name']
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

    def get_page(self, *args, **kwargs):
        records = []
        list_qs = models.HolidayList.objects.all()

        for list_id in list_qs.values_list('id', flat=True):
            records += self.client_call(list_id, *args, **kwargs)
        return records


class HolidayListSynchronizer(Synchronizer):
    client_class = api.ScheduleAPIClient
    model_class = models.HolidayListTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_holiday_lists(*args, **kwargs)


class SLAPrioritySynchronizer(Synchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.SlaPriorityTracker

    related_meta = {
        'priority': (models.TicketPriority, 'priority'),
        'sla': (models.Sla, 'sla')
    }

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.respond_hours = json_data['respondHours']
        instance.plan_within = json_data['planWithin']
        instance.resolution_hours = json_data['resolutionHours']

        self.set_relations(instance, json_data)
        return instance

    def client_call(self, sla_id, *args, **kwargs):
        return self.client.get_slapriorities(sla_id, *args, **kwargs)

    def get_page(self, *args, **kwargs):
        records = []
        sla_qs = models.Sla.objects.all()

        for sla_id in sla_qs.values_list('id', flat=True):
            records += self.client_call(sla_id, *args, **kwargs)

        return records


class SLASynchronizer(Synchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.SlaTracker

    related_meta = {
        'customCalendar': (models.Calendar, 'calendar'),
    }

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']
        instance.default_flag = json_data['defaultFlag']
        instance.respond_hours = json_data['respondHours']
        instance.plan_within = json_data['planWithin']
        instance.resolution_hours = json_data['resolutionHours']
        instance.based_on = json_data.get('basedOn')

        self.set_relations(instance, json_data)
        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_slas(*args, **kwargs)


class OpportunitySynchronizer(Synchronizer):
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
        instance.id = json_data['id']
        instance.name = json_data['name']
        instance.notes = json_data.get('notes')
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

    def get_page(self, *args, **kwargs):
        return self.client.get_opportunities(*args, **kwargs)

    def get_single(self, opportunity_id):
        return self.client.by_id(opportunity_id)


class OpportunityStageSynchronizer(Synchronizer):
    client_class = api.SalesAPIClient
    model_class = models.OpportunityStageTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_opportunity_stages(*args, **kwargs)


class OpportunityStatusSynchronizer(Synchronizer):
    client_class = api.SalesAPIClient
    model_class = models.OpportunityStatusTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']
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
        instance.id = json_data['id']
        instance.description = json_data['description']
        instance.inactive_flag = json_data['inactiveFlag']
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
        instance.id = json_data['id']
        instance.name = json_data['name']
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
        instance.id = json_data['id']
        instance.name = json_data['name']
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
        instance.id = json_data['id']
        instance.name = json_data['name']
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
        instance.id = json_data['id']
        instance.name = json_data['name']
        instance.inactive_flag = json_data['inactiveFlag']
        instance.overall_default_flag = json_data['overallDefaultFlag']
        if json_data['billTime'] == 'NoDefault':
            instance.bill_time = None
        else:
            instance.bill_time = json_data['billTime']

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_work_types(*args, **kwargs)


class WorkRoleSynchronizer(Synchronizer):
    client_class = api.TimeAPIClient
    model_class = models.WorkRoleTracker

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']
        instance.inactive_flag = json_data['inactiveFlag']

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_work_roles(*args, **kwargs)


class AgreementSynchronizer(Synchronizer):
    client_class = api.FinanceAPIClient
    model_class = models.AgreementTracker

    related_meta = {
        'workRole': (models.WorkRole, 'work_role'),
        'workType': (models.WorkType, 'work_type'),
        'company': (models.Company, 'company')
    }

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']
        instance.agreement_type = json_data['type']['name']
        instance.agreement_status = json_data.get('agreementStatus')
        instance.cancelled_flag = json_data['cancelledFlag']
        if json_data['billTime'] == 'NoDefault':
            instance.bill_time = None
        else:
            instance.bill_time = json_data['billTime']

        self.set_relations(instance, json_data)
        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_agreements(*args, **kwargs)


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
        instance.id = json_data['id']
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
