import logging

from dateutil.parser import parse
from copy import deepcopy
import math

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


DEFAULT_AVATAR_EXTENSION = 'jpg'
MAX_URL_LENGTH = 2000
MIN_URL_LENGTH = 1980

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
        created_count = updated_count = deleted_count = 0
        sync_job = models.SyncJob()
        sync_job.start_time = timezone.now()
        if sync_instance.full:
            sync_job.sync_type = 'full'
        else:
            sync_job.sync_type = 'partial'

        try:
            created_count, updated_count, deleted_count = f(*args, **kwargs)
            sync_job.success = True
        except Exception as e:
            sync_job.message = str(e.args[0])
            sync_job.success = False
            raise
        finally:
            sync_job.end_time = timezone.now()
            sync_job.entity_name = sync_instance.model_class.__name__
            sync_job.added = created_count
            sync_job.updated = updated_count
            sync_job.deleted = deleted_count
            sync_job.save()

        return created_count, updated_count, deleted_count
    return wrapper


class SyncResults:
    """Track results of a sync job."""
    def __init__(self):
        self.created_count = 0
        self.updated_count = 0
        self.deleted_count = 0
        self.synced_ids = set()


class Synchronizer:
    lookup_key = 'id'

    def __init__(self, full=False, *args, **kwargs):
        self.api_conditions = []
        self.client = self.client_class()
        request_settings = DjconnectwiseSettings().get_settings()
        self.batch_size = request_settings['batch_size']
        self.full = full

    @staticmethod
    def _assign_null_relation(instance, model_field):
        """
        Set the FK to null, but handle issues like the FK being non-null.

        This can happen because ConnectWise gives us records that point to
        non-existant records- such as activities whose assignTo fields point
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

        try:
            uid = relation_json['id']
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
            ids = self.model_class.objects.all().values_list(
                self.lookup_key, flat=True
            )
        else:
            ids = self.model_class.objects.filter(filter_params).values_list(
                self.lookup_key, flat=True
            )
        return set(ids)

    def get(self, results, conditions=None):
        """
        For all pages of results, save each page of results to the DB.

        If conditions is supplied in the call, then use only those conditions
        while fetching pages of records. If it's omitted, then use
        self.api_conditions.
        """
        page = 1
        while True:
            logger.info(
                'Fetching {} records, batch {}'.format(self.model_class, page)
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
                    _, created = self.update_or_create_instance(record)
                if created:
                    results.created_count += 1
                else:
                    results.updated_count += 1
            except InvalidObjectException as e:
                logger.warning('{}'.format(e))

            results.synced_ids.add(record['id'])

        return results

    def get_page(self, *args, **kwargs):
        raise NotImplementedError

    def get_single(self, *args, **kwargs):
        raise NotImplementedError

    def fetch_sync_by_id(self, instance_id):
        api_instance = self.get_single(instance_id)
        instance, created = self.update_or_create_instance(api_instance)
        return instance

    def fetch_delete_by_id(self, instance_id):
        try:
            self.get_single(instance_id)
        except api.ConnectWiseRecordNotFoundError:
            # This is what we expect to happen. Since it's gone in CW, we
            # are safe to delete it from here.
            self.model_class.objects.filter(pk=instance_id).delete()
            logger.info(
                'Deleted {} {} (if it existed).'.format(
                    self.model_class.__name__,
                    instance_id
                )
            )

    def update_or_create_instance(self, api_instance):
        """
        Creates and returns an instance if it does not already exist.
        """
        created = False
        try:
            instance_pk = api_instance[self.lookup_key]
            instance = self.model_class.objects.get(pk=instance_pk)
        except self.model_class.DoesNotExist:
            instance = self.model_class()
            created = True

        self._assign_field_data(instance, api_instance)
        instance.save()

        logger.info(
            '{}: {} {}'.format(
                'Created' if created else 'Updated',
                self.model_class.__name__,
                instance
            )
        )

        return instance, created

    def prune_stale_records(self, initial_ids, synced_ids):
        """
        Delete records that existed when sync started but were
        not seen as we iterated through all records from REST API.
        """
        stale_ids = initial_ids - synced_ids
        deleted_count = 0
        if stale_ids:
            delete_qset = self.model_class.objects.filter(pk__in=stale_ids)
            deleted_count = delete_qset.count()
            msg = 'Removing {} stale records for model: {}'.format(
                len(stale_ids), self.model_class,
            )
            logger.info(msg)
            delete_qset.delete()

        return deleted_count

    @log_sync_job
    def sync(self):
        sync_job_qset = models.SyncJob.objects.filter(
            entity_name=self.model_class.__name__
        )

        if sync_job_qset.exists() and not self.full:
            last_sync_job_time = sync_job_qset.last().start_time.isoformat()
            self.api_conditions.append(
                "lastUpdated>[{0}]".format(last_sync_job_time)
            )
        results = SyncResults()
        initial_ids = self._instance_ids()  # Set of IDs of all records prior
        # to sync, to find stale records for deletion.
        results = self.get(results, )

        if self.full:
            results.deleted_count = self.prune_stale_records(
                initial_ids, results.synced_ids
            )

        return results.created_count, results.updated_count, \
            results.deleted_count

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
            results.deleted_count

    def sync_children(self, *args):
        for synchronizer, filter_params in args:
            created_count, updated_count, \
                deleted_count = synchronizer.callback_sync(filter_params)
            msg = '{} Child Sync - Created: {},'\
                ' Updated: {}, Deleted: {}'.format(
                    synchronizer.model_class.__name__,
                    created_count,
                    updated_count,
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


class ServiceNoteSynchronizer(Synchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.ServiceNote

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
                ' ObjectDoesNotExist Exception: '.format(instance.id, e)
            )

        for json_field, value in self.related_meta.items():
            model_class, field_name = value
            self._assign_relation(
                instance,
                json_data,
                json_field,
                model_class,
                field_name
            )

    def client_call(self, ticket_id, *args, **kwargs):
        return self.client.get_notes(ticket_id, *args, **kwargs)

    def get_page(self, *args, **kwargs):
        records = []
        ticket_qs = models.Ticket.objects.all()

        # We are using the conditions here to specify getting a single
        # tickets notes, and then overwriting it, because only a number
        # was supplied, which cant acutally be used later on. When it is
        # being synced by huey it will append a 'lastUpdated' condition
        # after this point, so we are free to use conditions to select
        # one ticket in this strange way without disrupting any other
        # functionality.
        # If in the future we DO want to add conditions, this will have to
        # be modified. That may never happen though, so it is probably
        # fine like this for the forseeable future.
        if kwargs['conditions']:
            try:
                ticket_id = int(kwargs['conditions'][0])
                kwargs['conditions'] = []
                records += self.client_call(ticket_id, *args, **kwargs)

                return records
            except ValueError:
                # Do nothing
                pass
        for ticket_id in ticket_qs.values_list('id', flat=True):
            records += self.client_call(ticket_id, *args, **kwargs)

        return records


class OpportunityNoteSynchronizer(Synchronizer):
    client_class = api.SalesAPIClient
    model_class = models.OpportunityNote

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.text = json_data.get('text')

        opp_class = models.Opportunity

        instance.date_created = json_data.get('_info').get('lastUpdated')

        try:
            opportunity_id = json_data.get('opportunityId')
            related_opportunity = opp_class.objects.get(pk=opportunity_id)
            setattr(instance, 'opportunity', related_opportunity)
        except ObjectDoesNotExist as e:
            logger.warning(
                'Opportunity not found for {}.'.format(instance.id) +
                ' ObjectDoesNotExist Exception: {}'.format(e)
            )

    def client_call(self, opportunity_id, *args, **kwargs):
        return self.client.get_notes(opportunity_id, *args, **kwargs)

    def get_page(self, *args, **kwargs):
        records = []
        opportunity_qs = models.Opportunity.objects.all()

        for opportunity_id in opportunity_qs.values_list('id', flat=True):
            records += self.client_call(opportunity_id, *args, **kwargs)

        return records


class BoardSynchronizer(Synchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.ConnectWiseBoard

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']
        if 'inactiveFlag' in json_data:
            # This is the new CW way
            instance.inactive = json_data.get('inactiveFlag')
        else:
            # This is old, but keep for backwards-compatibility
            instance.inactive = json_data.get('inactive')
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

    def get_page(self, *args, **kwargs):
        records = []
        board_qs = models.ConnectWiseBoard.objects.all()

        for board_id in board_qs.values_list('id', flat=True):
            records += self.client_call(board_id, *args, **kwargs)

        return records


class BoardStatusSynchronizer(BoardChildSynchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.BoardStatus

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

        return instance

    def client_call(self, board_id, *args, **kwargs):
        kwargs['conditions'] = self.api_conditions
        return self.client.get_statuses(board_id, *args, **kwargs)


class TeamSynchronizer(BoardChildSynchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.Team

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
    model_class = models.Company

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_conditions = ['deletedFlag=False']

    def _assign_field_data(self, company, company_json):
        """
        Assigns field data from an company_json instance
        to a local Company model instance
        """
        company_json = self.remove_null_characters(company_json)

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
        company.created = timezone.now()
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

        type_json = company_json.get('type')
        if type_json:
            try:
                company_type = models.CompanyType.objects.get(
                    pk=type_json['id'])
                company.company_type = company_type
            except models.CompanyType.DoesNotExist:
                logger.warning(
                    'Failed to find CompanyType: {}'.format(
                        type_json['id']
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

        company.save()
        return company

    def get_page(self, *args, **kwargs):
        return self.client.get_companies(*args, **kwargs)

    def get_single(self, company_id):
        return self.client.by_id(company_id)

    def fetch_delete_by_id(self, company_id):
        # Companies are deleted by setting deleted_flag = True, so
        # just treat this as a normal sync.
        self.fetch_sync_by_id(company_id)


class CompanyStatusSynchronizer(Synchronizer):
    client_class = api.CompanyAPIClient
    model_class = models.CompanyStatus

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
    model_class = models.CompanyType

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data.get('name')
        instance.vendor_flag = json_data['vendorFlag']

    def get_page(self, *args, **kwargs):
        return self.client.get_company_types(*args, **kwargs)


class MyCompanyOtherSynchronizer(Synchronizer):
    client_class = api.SystemAPIClient
    model_class = models.MyCompanyOther

    related_meta = {
        'defaultCalendar': (models.Calendar, 'default_calendar'),
    }

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']

        for json_field, value in self.related_meta.items():
            model_class, field_name = value
            self._assign_relation(
                instance,
                json_data,
                json_field,
                model_class,
                field_name
            )

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_mycompanyother(*args, **kwargs)


class ActivitySynchronizer(Synchronizer):
    client_class = api.SalesAPIClient
    model_class = models.Activity

    related_meta = {
        'opportunity': (models.Opportunity, 'opportunity'),
        'ticket': (models.Ticket, 'ticket'),
        'assignTo': (models.Member, 'assign_to'),
    }

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

        # Assign foreign keys
        for json_field, value in self.related_meta.items():
            model_class, field_name = value
            self._assign_relation(
                instance,
                json_data,
                json_field,
                model_class,
                field_name
            )

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_activities(*args, **kwargs)

    def get_single(self, activity_id):
        return self.client.get_single_activity(activity_id)


class SalesProbabilitySynchronizer(Synchronizer):
    client_class = api.SalesAPIClient
    model_class = models.SalesProbability

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.probability = json_data['probability']

    def get_page(self, *args, **kwargs):
        return self.client.get_probabilities(*args, **kwargs)


class ScheduleEntriesSynchronizer(BatchConditionMixin, Synchronizer):
    client_class = api.ScheduleAPIClient
    model_class = models.ScheduleEntry
    batch_condition_list = []

    related_meta = {
        'where': (models.Location, 'where'),
        'status': (models.ScheduleStatus, 'status'),
        'type': (models.ScheduleType, 'schedule_type'),
        'member': (models.Member, 'member')
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_conditions = [
            "(type/identifier='S' or type/identifier='O')",
            "doneFlag=false",
        ]
        # Only get schedule entries for tickets or opportunities that we
        # already have in the DB.
        ticket_ids = set(
            models.Ticket.objects.values_list('id', flat=True)
        )
        opportunity_ids = set(
            models.Opportunity.objects.values_list('id', flat=True)
        )
        self.batch_condition_list = list(ticket_ids | opportunity_ids)

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
        expected_date_start = json_data.get('dateStart')
        if expected_date_start:
            instance.expected_date_start = parse(expected_date_start)

        expected_date_end = json_data.get('dateEnd')
        if expected_date_end:
            instance.expected_date_end = parse(expected_date_end)

        # handle foreign keys
        for json_field, value in self.related_meta.items():
            model_class, field_name = value
            self._assign_relation(
                instance,
                json_data,
                json_field,
                model_class,
                field_name
            )
        # _assign_relation expects a dict. objectId is an integer. Handle it
        # as a special situation.
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

    def create_new_entry(self, *args, **kwargs):
        """
        Send POST request to ConnectWise to create a new entry and then
        create it in the local database from the response
        """
        schedule_client = api.ScheduleAPIClient()
        instance = schedule_client.post_schedule_entry(*args, **kwargs)
        return self.update_or_create_instance(instance)


class ScheduleStatusSynchronizer(Synchronizer):
    client_class = api.ScheduleAPIClient
    model_class = models.ScheduleStatus

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_schedule_statuses(*args, **kwargs)


class ScheduleTypeSychronizer(Synchronizer):
    client_class = api.ScheduleAPIClient
    model_class = models.ScheduleType

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']
        instance.identifier = json_data['identifier']

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_schedule_types(*args, **kwargs)


class TerritorySynchronizer(Synchronizer):
    client_class = api.SystemAPIClient
    model_class = models.Territory

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_territories(*args, **kwargs)


class TimeEntrySynchronizer(BatchConditionMixin, Synchronizer):
    client_class = api.TimeAPIClient
    model_class = models.TimeEntry
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
            models.Ticket.objects.values_list('id', flat=True)
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

        hours_deduct = json_data.get('hoursDeduct')
        if hours_deduct:
            instance.hours_deduct = hours_deduct

        actual_hours = json_data.get('actualHours')
        if actual_hours:
            instance.actual_hours = actual_hours

        detail_description_flag = json_data.get('addToDetailDescriptionFlag')
        if detail_description_flag:
            instance.detail_description_flag = detail_description_flag

        internal_analysis_flag = json_data.get('addToInternalAnalysisFlag')
        if internal_analysis_flag:
            instance.internal_analysis_flag = internal_analysis_flag

        resolution_flag = json_data.get('addToResolutionFlag')
        if resolution_flag:
            instance.resolution_flag = resolution_flag

        for json_field, value in self.related_meta.items():
            model_class, field_name = value
            self._assign_relation(
                instance,
                json_data,
                json_field,
                model_class,
                field_name
            )

        # Similar to Schedule Entries, chargeToId is stored as an int in
        # ConnectWise, handled as special situation
        # Not making a method to handle this in a similar way to Schedule
        # entries and even with the similar code
        # as this may be VERY different in the near future, because
        # charge_to_id would be converted to a GenericForeignKey
        # and would be handled differently
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


class LocationSynchronizer(Synchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.Location

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
    model_class = models.TicketPriority

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
    model_class = models.ProjectStatus

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']
        instance.default_flag = json_data.get('defaultFlag')
        instance.inactive_flag = json_data.get('inactiveFlag')
        instance.closed_flag = json_data.get('closedFlag')
        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_project_statuses(*args, **kwargs)


class ProjectSynchronizer(Synchronizer):
    client_class = api.ProjectAPIClient
    model_class = models.Project
    related_meta = {
        'status': (models.ProjectStatus, 'status'),
        'manager': (models.Member, 'manager')
    }

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']
        instance.actual_hours = json_data.get('actualHours')
        instance.budget_hours = json_data.get('budgetHours')
        instance.scheduled_hours = json_data.get('scheduledHours')

        # handle foreign keys
        for json_field, value in self.related_meta.items():
            model_class, field_name = value
            self._assign_relation(instance,
                                  json_data,
                                  json_field,
                                  model_class,
                                  field_name)

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_projects(*args, **kwargs)

    def get_single(self, project_id):
        return self.client.get_project(project_id)


class MemberSynchronizer(Synchronizer):
    client_class = api.SystemAPIClient
    model_class = models.Member

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_sync_job_time = None

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.first_name = json_data.get('firstName')
        instance.last_name = json_data.get('lastName')
        instance.identifier = json_data.get('identifier')
        instance.office_email = json_data.get('officeEmail')
        if instance.office_email is None:
            raise InvalidObjectException(
                'Office email of user {} is null- skipping.'
                .format(instance.identifier)
            )
        instance.license_class = json_data.get('licenseClass')
        instance.inactive = json_data.get('inactiveFlag')
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

    def get_page(self, *args, **kwargs):
        return self.client.get_members(*args, **kwargs)

    def update_or_create_instance(self, api_instance):
        """
        In addition to what the parent does, also update avatar if necessary.
        """
        try:
            instance, created = super().update_or_create_instance(api_instance)
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
            remove_thumbnail(instance.avatar)
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
                         created):
            logger.info(
                'Fetching avatar for member {}.'.format(username)
            )
            (attachment_filename, avatar) = self.client \
                .get_member_image_by_photo_id(photo_id, username)
            if attachment_filename and avatar:
                self._save_avatar(instance, avatar, attachment_filename)
            instance.save()

        return instance, created


class TicketSynchronizer(BatchConditionMixin, Synchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.Ticket
    batch_condition_list = []

    related_meta = {
        'team': (models.Team, 'team'),
        'board': (models.ConnectWiseBoard, 'board'),
        'company': (models.Company, 'company'),
        'priority': (models.TicketPriority, 'priority'),
        'project': (models.Project, 'project'),
        'serviceLocation': (models.Location, 'location'),
        'status': (models.BoardStatus, 'status'),
        'owner': (models.Member, 'owner'),
        'sla': (models.Sla, 'sla'),
        'type': (models.Type, 'type'),
        'subType': (models.SubType, 'sub_type'),
        'item': (models.Item, 'sub_type_item')
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_conditions = ['closedFlag=False']
        # To get all open tickets, we can simply supply a `closedFlag=False`
        # condition for on-premise ConnectWise. But for hosted ConnectWise,
        # this results in timeouts for requests, so we also need to add a
        # condition for all the open statuses. This doesn't impact on-premise
        # ConnectWise, so we just do it for all cases.
        open_statuses = list(
            models.BoardStatus.available_objects.
            filter(closed_status=False).
            values_list('id', flat=True)
        )
        if open_statuses:
            # Only do this if we know of at least one open status.
            self.batch_condition_list = open_statuses

    def _assign_field_data(self, instance, json_data):
        created = instance.id is None
        # If the status results in a move to a different column
        original_status = not created and instance.status or None

        json_data_id = json_data['id']
        instance.id = json_data['id']
        instance.summary = json_data['summary']
        instance.closed_flag = json_data.get('closedFlag')
        instance.entered_date_utc = parse(json_data.get('dateEntered'))
        instance.last_updated_utc = json_data.get('_info').get('lastUpdated')
        instance.required_date_utc = json_data.get('requiredDate')
        instance.resources = json_data.get('resources')
        instance.budget_hours = json_data.get('budgetHours')
        instance.actual_hours = json_data.get('actualHours')
        instance.record_type = json_data.get('recordType')
        instance.parent_ticket_id = json_data.get('parentTicketId')
        instance.has_child_ticket = json_data.get('hasChildTicket')
        instance.customer_updated = json_data.get('customerUpdatedFlag')
        instance.respond_mins = json_data.get('respondMinutes')
        instance.res_plan_mins = json_data.get('resPlanMinutes')
        instance.resolve_mins = json_data.get('resolveMinutes')
        instance.date_resolved_utc = json_data.get('dateResolved')
        instance.date_resplan_utc = json_data.get('dateResplan')
        instance.date_responded_utc = json_data.get('dateResponded')

        for json_field, value in self.related_meta.items():
            model_class, field_name = value
            self._assign_relation(
                instance,
                json_data,
                json_field,
                model_class,
                field_name
            )

        instance.save()

        logger.info('Syncing ticket {}'.format(json_data_id))
        action = created and 'Created' or 'Updated'

        status_changed = ''
        if original_status != instance.status:
            status_changed = '; status changed from ' \
                '{} to {}'.format(original_status, instance.status)

        log_info = '{} ticket {}{}'.format(
            action, instance.id, status_changed
        )
        logger.info(log_info)

        return instance

    def sync_related(self, instance):
        instance_id = instance.id
        sync_classes = []

        sched_sync = ScheduleEntriesSynchronizer()
        sched_sync.batch_condition_list = [instance_id]
        sync_classes.append((sched_sync, Q(ticket_object=instance)))

        note_sync = ServiceNoteSynchronizer()
        note_sync.api_conditions = [instance_id]
        sync_classes.append((note_sync, Q(ticket=instance)))

        time_sync = TimeEntrySynchronizer()
        time_sync.batch_condition_list = [instance_id]
        sync_classes.append((time_sync, Q(charge_to_id=instance)))

        self.sync_children(*sync_classes)

    def get_batch_condition(self, conditions):
        return 'status/id in ({})'.format(
            ','.join([str(i) for i in conditions])
        )

    def get_page(self, *args, **kwargs):
        return self.client.get_tickets(*args, **kwargs)

    def get_single(self, ticket_id):
        return self.client.get_ticket(ticket_id)

    def fetch_sync_by_id(self, instance_id):
        instance = super().fetch_sync_by_id(instance_id)
        if not instance.closed_flag:
            self.sync_related(instance)
        return instance


class CalendarSynchronizer(Synchronizer):
    client_class = api.ScheduleAPIClient
    model_class = models.Calendar

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']
        instance.monday_start_time = json_data.get('mondayStartTime')
        instance.monday_end_time = json_data.get('mondayEndTime')
        instance.tuesday_start_time = json_data.get('tuesdayStartTime')
        instance.tuesday_end_time = json_data.get('tuesdayEndTime')
        instance.wednesday_start_time = json_data.get('wednesdayStartTime')
        instance.wednesday_end_time = json_data.get('wednesdayEndTime')
        instance.thursday_start_time = json_data.get('thursdayStartTime')
        instance.thursday_end_time = json_data.get('thursdayEndTime')
        instance.friday_start_time = json_data.get('fridayStartTime')
        instance.friday_end_time = json_data.get('fridayEndTime')
        instance.saturday_start_time = json_data.get('saturdayStartTime')
        instance.saturday_end_time = json_data.get('saturdayEndTime')
        instance.sunday_start_time = json_data.get('sundayStartTime')
        instance.sunday_end_time = json_data.get('sundayEndTime')

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
    model_class = models.Holiday

    def _assign_field_data(self, instance, json_data):

        instance.id = json_data['id']
        instance.name = json_data['name']
        instance.all_day_flag = json_data.get('allDayFlag')
        instance.date = json_data.get('date')
        instance.start_time = json_data.get('timeStart')
        instance.end_time = json_data.get('timeEnd')

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
    model_class = models.HolidayList

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_holiday_lists(*args, **kwargs)


class SLAPrioritySychronizer(Synchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.SlaPriority

    related_meta = {
        'priority': (models.TicketPriority, 'priority'),
        'sla': (models.Sla, 'sla')
    }

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.respond_hours = json_data['respondHours']
        instance.plan_within = json_data['planWithin']
        instance.resolution_hours = json_data['resolutionHours']

        for json_field, value in self.related_meta.items():
            model_class, field_name = value
            self._assign_relation(
                instance,
                json_data,
                json_field,
                model_class,
                field_name
            )

        instance.save()

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
    model_class = models.Sla

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

        for json_field, value in self.related_meta.items():
            model_class, field_name = value
            self._assign_relation(
                instance,
                json_data,
                json_field,
                model_class,
                field_name
            )

        instance.save()

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_slas(*args, **kwargs)


class OpportunitySynchronizer(Synchronizer):
    client_class = api.SalesAPIClient
    model_class = models.Opportunity
    related_meta = {
        'type': (models.OpportunityType, 'opportunity_type'),
        'stage': (models.OpportunityStage, 'stage'),
        'status': (models.OpportunityStatus, 'status'),
        'probability': (models.SalesProbability, 'probability'),
        'primarySalesRep': (models.Member, 'primary_sales_rep'),
        'secondarySalesRep': (models.Member, 'secondary_sales_rep'),
        'company': (models.Company, 'company'),
        'closedBy': (models.Member, 'closed_by')
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # only synchronize Opportunities that do not have an OpportunityStatus
        # with the closedFlag=True
        open_statuses = list(
            models.OpportunityStatus.objects.
            filter(closed_flag=False).
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
                models.OpportunityPriority, priority
            )

        # handle foreign keys
        for json_field, value in self.related_meta.items():
            model_class, field_name = value
            self._assign_relation(instance,
                                  json_data,
                                  json_field,
                                  model_class,
                                  field_name)

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_opportunities(*args, **kwargs)

    def get_single(self, opportunity_id):
        return self.client.by_id(opportunity_id)


class OpportunityStageSynchronizer(Synchronizer):
    client_class = api.SalesAPIClient
    model_class = models.OpportunityStage

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_opportunity_stages(*args, **kwargs)


class OpportunityStatusSynchronizer(Synchronizer):
    client_class = api.SalesAPIClient
    model_class = models.OpportunityStatus

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
    model_class = models.OpportunityType

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.description = json_data['description']
        instance.inactive_flag = json_data['inactiveFlag']
        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_opportunity_types(*args, **kwargs)


class TypeSynchronizer(Synchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.Type

    related_meta = {
        'board': (models.ConnectWiseBoard, 'board')
    }

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']

        for json_field, value in self.related_meta.items():
            model_class, field_name = value
            self._assign_relation(
                instance,
                json_data,
                json_field,
                model_class,
                field_name
            )

        instance.save()

        return instance

    def client_call(self, board_id, *args, **kwargs):
        return self.client.get_types(board_id, *args, **kwargs)

    def get_page(self, *args, **kwargs):
        records = []
        board_qs = models.ConnectWiseBoard.objects.all()

        for board_id in board_qs.values_list('id', flat=True):
            records += self.client_call(board_id, *args, **kwargs)

        return records


class SubTypeSynchronizer(Synchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.SubType

    related_meta = {
        'board': (models.ConnectWiseBoard, 'board')
    }

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']

        for json_field, value in self.related_meta.items():
            model_class, field_name = value
            self._assign_relation(
                instance,
                json_data,
                json_field,
                model_class,
                field_name
            )

        instance.save()

        return instance

    def client_call(self, board_id, *args, **kwargs):
        return self.client.get_subtypes(board_id, *args, **kwargs)

    def get_page(self, *args, **kwargs):
        records = []
        board_qs = models.ConnectWiseBoard.objects.all()

        for board_id in board_qs.values_list('id', flat=True):
            records += self.client_call(board_id, *args, **kwargs)

        return records


class ItemSynchronizer(Synchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.Item

    related_meta = {
        'board': (models.ConnectWiseBoard, 'board')
    }

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']

        for json_field, value in self.related_meta.items():
            model_class, field_name = value
            self._assign_relation(
                instance,
                json_data,
                json_field,
                model_class,
                field_name
            )

        instance.save()

        return instance

    def client_call(self, board_id, *args, **kwargs):
        return self.client.get_items(board_id, *args, **kwargs)

    def get_page(self, *args, **kwargs):
        records = []
        board_qs = models.ConnectWiseBoard.objects.all()

        for board_id in board_qs.values_list('id', flat=True):
            records += self.client_call(board_id, *args, **kwargs)

        return records
