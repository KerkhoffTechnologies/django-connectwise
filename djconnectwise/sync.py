import logging

from dateutil.parser import parse

from django.core.files.base import ContentFile
from django.utils import timezone

from djconnectwise import api
from djconnectwise import models
from djconnectwise.utils import get_hash, get_filename_extension
from djconnectwise.utils import RequestSettings


DEFAULT_AVATAR_EXTENSION = 'jpg'

logger = logging.getLogger(__name__)


def log_sync_job(f):
    def wrapper(*args, **kwargs):
        sync_instance = args[0]
        created_count = updated_count = deleted_count = 0
        sync_job = models.SyncJob()
        sync_job.start_time = timezone.now()

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


class Synchronizer:
    lookup_key = 'id'
    api_conditions = []

    def __init__(self, *args, **kwargs):
        self.instance_map = {}
        self.client = self.client_class()
        self.load_instance_map()

        request_settings = RequestSettings().get_settings()
        self.batch_size = request_settings['batch_size']

    def _assign_relation(self, ticket, json_data,
                         json_field, model_class, model_field):
        relation_json = json_data.get(json_field)
        if relation_json:
            try:
                uid = relation_json['id']
                related_instance = model_class.objects.get(pk=uid)
                setattr(ticket, model_field, related_instance)
            except model_class.DoesNotExist:
                logger.warning(
                    'Failed to find {} {} for ticket {}.'.format(
                        json_field,
                        uid,
                        ticket.id
                    )
                )

    def load_instance_map(self):
        qset = self.get_queryset()
        self.instance_map = {
            getattr(i, self.lookup_key): i for i in qset
        }

    def get_queryset(self):
        return self.model_class.objects.all()

    def get(self):
        """Buffer and return all pages of results."""
        records = []
        page = 1
        while True:
            logger.info(
                'Fetching {} records, batch {}'.format(self.model_class, page)
            )
            page_records = self.get_page(
                page=page, page_size=self.batch_size
            )
            records += page_records
            page += 1
            if len(page_records) < self.batch_size:
                # This page wasn't full, so there's no more records after
                # this page.
                break
        return records

    def get_page(self, *args, **kwargs):
        raise NotImplementedError

    def fetch_sync_by_id(self, *args, **kwargs):
        raise NotImplementedError

    def fetch_delete_by_id(self, *args, **kwargs):
        raise NotImplementedError

    def get_or_create_instance(self, api_instance):
        lookup_key = api_instance[self.lookup_key]
        instance = self.instance_map.get(lookup_key)

        created = False

        if not instance:
            instance = self.model_class()
            self._assign_field_data(instance, api_instance)
            instance.save()
            created = True
            self.instance_map[lookup_key] = instance

        return instance, created

    def prune_stale_records(self, synced_ids):
        stale_ids = set(self.instance_map.keys()) - synced_ids
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

    def update_or_create_instance(self, api_instance):
        """
        Creates and returns an instance if it does not already exist.
        """
        instance, created = self.get_or_create_instance(
            api_instance)

        action = 'Created' if created else 'Updated'
        if not created:
            self._assign_field_data(instance, api_instance)
            instance.save()

        self.instance_map[instance.id] = instance

        msg = ' {}: {} {}'
        logger.info(msg.format(action, self.model_class.__name__, instance))

        return instance, created

    @log_sync_job
    def sync(self, reset=False):
        created_count = 0
        updated_count = 0
        deleted_count = 0

        synced_ids = set()
        for record in self.get():

            _, created = self.update_or_create_instance(record)
            if created:
                created_count += 1
            else:
                updated_count += 1

            synced_ids.add(record['id'])

        stale_ids = set(self.instance_map.keys()) - synced_ids
        if stale_ids and reset:
            deleted_count = len(stale_ids)
            msg = 'Removing {} stale records for model: {}'.format(
                len(stale_ids), self.model_class,
            )
            logger.info(msg)
            self.model_class.objects.filter(pk__in=stale_ids).delete()
        return created_count, updated_count, deleted_count


class BoardSynchronizer(Synchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.ConnectWiseBoard

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']
        instance.inactive = json_data.get('inactive')
        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_boards(*args, **kwargs)

    def get_queryset(self):
        return self.model_class.objects.all()


class BoardChildSynchronizer(Synchronizer):

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']
        instance.board = models.ConnectWiseBoard.objects.get(
            id=json_data['boardId'])
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

    def _assign_field_data(self, instance, json_data):
        instance = super(BoardStatusSynchronizer, self)._assign_field_data(
            instance, json_data)

        instance.sort_order = json_data.get('sortOrder')
        instance.display_on_board = json_data.get('displayOnBoard')
        instance.inactive = json_data.get('inactive')
        instance.closed_status = json_data.get('closedStatus')

        return instance

    def client_call(self, board_id, *args, **kwargs):
        return self.client.get_statuses(board_id, *args, **kwargs)

    def get_queryset(self):
        return self.model_class.objects.all()


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
    """
    Coordinates retrieval and demarshalling of ConnectWise JSON
    Company instances.
    """
    client_class = api.CompanyAPIClient
    model_class = models.Company
    api_conditions = ['deletedFlag=False']

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
        company.save()
        return company

    def get_page(self, *args, **kwargs):
        kwargs['conditions'] = self.api_conditions
        return self.client.get_companies(*args, **kwargs)

    def get_queryset(self):
        return self.model_class.objects.all()

    def fetch_sync_by_id(self, company_id):
        company = self.client.by_id(company_id)
        self.update_or_create_instance(company)

    def fetch_delete_by_id(self, company_id):
        # Companies are deleted by setting deleted_flag = True, so
        # just treat this as a normal sync.
        self.fetch_sync_by_id(company_id)


class CompanyStatusSynchronizer(Synchronizer):
    """
    Coordinates retrieval and demarshalling of ConnectWise JSON
    CompanyStatus instances.
    """
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


class LocationSynchronizer(Synchronizer):
    """
    Coordinates retrieval and demarshalling of ConnectWise JSON
    Location instances.
    """
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


class ProjectSynchronizer(Synchronizer):
    client_class = api.ProjectAPIClient
    model_class = models.Project

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']
        instance.status_name = json_data['status']['name']
        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_projects(*args, **kwargs)

    def get_queryset(self):
        return self.model_class.objects.all()

    def fetch_sync_by_id(self, project_id):
        project = self.client.get_project(project_id)
        self.update_or_create_instance(project)
        logger.info('Updated project {}'.format(project))

    def fetch_delete_by_id(self, project_id):
        try:
            self.client.get_project(project_id)
        except api.ConnectWiseRecordNotFoundError:
            # This is what we expect to happen. Since it's gone in CW, we
            # are safe to delete it from here.
            models.Project.objects.filter(id=project_id).delete()
            logger.info(
                'Deleted project {} (if it existed).'.format(project_id)
            )


class MemberSynchronizer(Synchronizer):
    client_class = api.SystemAPIClient
    model_class = models.Member

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_sync_job = None

        sync_job_qset = models.SyncJob.objects.filter(
            entity_name=self.model_class.__name__)

        if sync_job_qset.exists():
            self.last_sync_job = sync_job_qset.last()

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.first_name = json_data.get('firstName')
        instance.last_name = json_data.get('lastName')
        instance.identifier = json_data.get('identifier')
        instance.office_email = json_data.get('officeEmail')
        instance.license_class = json_data.get('licenseClass')
        instance.inactive = json_data.get('inactiveFlag')
        return instance

    def _save_avatar(self, member, avatar, attachment_filename):
        """
        The Django ImageField (and ThumbnailerImageField) field adjusts our
        filename if the file already exists- it adds some random characters at
        the end of the name. This means if we just save a new image when the
        old one still exists, we'll get a new image for each save, resulting
        in lots of unnecessary images. So we'll delete the old image first,
        and then the save will use the exact name we give it.

        Well, except in the case where two or more members share the same
        image, because we're using content hashes as names, and ConnectWise
        gives users a common default avatar. In that case, the first save
        will use the expected name, while subsequent saves for other members
        will have some random characters added to the filename.

        This method tells Django not to call save() on the given model,
        so the caller must be sure to do that itself.
        """
        extension = get_filename_extension(attachment_filename)
        filename = '{}.{}'.format(
            get_hash(avatar), extension or DEFAULT_AVATAR_EXTENSION)
        avatar_file = ContentFile(avatar)
        member.avatar.delete(save=False)
        member.avatar.save(filename, avatar_file, save=False)
        logger.info("Saved member '{}' avatar to {}.".format(
            member.identifier, member.avatar.name))

    def get(self):
        records = []
        page = 1
        while True:
            logger.info(
                'Fetching member records, batch {}'.format(page)
            )
            page_records = self.get_page(
                page=page, page_size=self.batch_size
            )
            records += page_records
            page += 1
            if len(page_records) < self.batch_size:
                # No more records
                break
        return records

    def get_page(self, *args, **kwargs):
        return self.client.get_members(*args, **kwargs)

    @log_sync_job
    def sync(self, reset=False):
        members_json = self.get()

        updated_count = 0
        created_count = 0
        deleted_count = 0
        synced_ids = set()

        for api_member in members_json:
            member_id = api_member['id']
            username = api_member['identifier']

            try:
                member = models.Member.objects.get(id=member_id)
                self._assign_field_data(member, api_member)
                member.save()
                updated_count += 1
                logger.info('Updated member: {0}'.format(member.identifier))
            except models.Member.DoesNotExist:
                # Member with that ID wasn't found, so let's make one.
                member = models.Member()
                self._assign_field_data(member, api_member)
                member.save()
                created_count += 1
                logger.info('Created member: {0}'.format(member.identifier))

            # Only update the avatar if the member profile
            # was updated since last sync.
            member_last_updated = parse(api_member['_info']['lastUpdated'])
            logger.debug(
                'Member {} last updated: {}'.format(
                    member.identifier,
                    member_last_updated
                )
            )
            member_stale = False
            if self.last_sync_job:
                member_stale = member_last_updated > \
                    self.last_sync_job.start_time

            if not self.last_sync_job or member_stale:
                logger.debug(
                    'Fetching avatar for member {}.'.format(member.identifier)
                )
                (attachment_filename, avatar) = self.client \
                    .get_member_image_by_identifier(username)
                if attachment_filename and avatar:
                    self._save_avatar(member, avatar, attachment_filename)

            member.save()
            synced_ids.add(api_member['id'])

        if reset:
            deleted_count = self.prune_stale_records(synced_ids)

        return created_count, updated_count, deleted_count


class TicketSynchronizer(Synchronizer):
    """
    Coordinates retrieval and demarshalling of ConnectWise JSON
    objects to the local counterparts.
    """
    client_class = api.ServiceAPIClient
    model_class = models.Ticket
    api_conditions = ['closedFlag = False']
    child_synchronizers = (
        CompanySynchronizer,
        BoardStatusSynchronizer,
        PrioritySynchronizer,
        LocationSynchronizer
    )

    related_meta = {
        'team': (models.Team, 'team'),
        'board': (models.ConnectWiseBoard, 'board'),
        'company': (models.Company, 'company'),
        'priority': (models.TicketPriority, 'priority'),
        'project': (models.Project, 'project'),
        'serviceLocation': (models.Location, 'location'),
        'status': (models.BoardStatus, 'status'),
        'owner': (models.Member, 'owner')
    }

    def __init__(self):
        super().__init__()
        self.members_map = {
            m.identifier: m for m in models.Member.objects.all()
        }
        # To get all open tickets, we can simply supply a `closedFlag=False`
        # condition for on-premise ConnectWise. But for hosted ConnectWise,
        # this results in timeouts for requests, so we also need to add a
        # condition for all the open statuses. This doesn't impact on-premise
        # ConnectWise, so we just do it for all cases.
        open_statuses = models.BoardStatus.available_objects.\
            filter(closed_status=False).values_list('id', flat=True)
        if open_statuses:
            # Only do this if we know of at least one open status.
            open_statuses_condition = 'status/id in ({})'.format(
                ','.join([str(i) for i in open_statuses])
            )
            self.api_conditions.append(open_statuses_condition)

    def _assign_field_data(self, instance, json_data):
        created = instance.id is None
        # If the status results in a move to a different column
        original_status = not created and instance.status or None

        json_data_id = json_data['id']
        instance.api_text = str(json_data)
        instance.id = json_data['id']
        instance.summary = json_data['summary']
        instance.closed_flag = json_data.get('closedFlag')
        instance.type = json_data.get('type')
        instance.entered_date_utc = json_data.get('dateEntered')
        instance.last_updated_utc = json_data.get('_info').get('lastUpdated')
        instance.required_date_utc = json_data.get('requiredDate')
        instance.resources = json_data.get('resources')
        instance.budget_hours = json_data.get('budgetHours')
        instance.actual_hours = json_data.get('actualHours')
        instance.record_type = json_data.get('recordType')
        instance.parent_ticket_id = json_data.get('parentTicketId')
        instance.has_child_ticket = json_data.get('hasChildTicket')
        instance.customer_updated = json_data.get('customerUpdatedFlag')

        for json_field, value in self.related_meta.items():
            model_class, field_name = value
            self._assign_relation(instance,
                                  json_data,
                                  json_field,
                                  model_class,
                                  field_name)

        instance.save()
        self._manage_member_assignments(instance)

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

    def _manage_member_assignments(self, ticket):
        if not ticket.resources:
            ticket.members.clear()
            return

        ticket_assignments = {}
        usernames = [
            u.strip() for u in ticket.resources.split(',')
        ]
        # Reset board/ticket assignment in case the assigned resources
        # have changed since last sync.
        models.TicketAssignment.objects.filter(
            ticket=ticket).delete()
        for username in usernames:
            member = self.members_map.get(username)

            if member:
                assignment = models.TicketAssignment()
                assignment.member = member
                assignment.ticket = ticket
                ticket_assignments[(username, ticket.id,)] = \
                    assignment
                msg = 'Member ticket assignment: ' \
                      'ticket {}, member {}'.format(ticket.id, username)
                logger.info(msg)
            else:
                logger.warning(
                    'Failed to locate member with username {} for ticket '
                    '{} assignment.'.format(username, ticket.id)
                )

        if ticket_assignments:
            logger.info(
                'Saving {} ticket assignments'.format(
                    len(ticket_assignments)
                )
            )
            models.TicketAssignment.objects.bulk_create(
                list(ticket_assignments.values())
            )

    def get_page(self, *args, **kwargs):
        kwargs['conditions'] = self.api_conditions
        return self.client.get_tickets(*args, **kwargs)

    def get_queryset(self):
        return self.model_class.objects.all()

    def fetch_sync_by_id(self, ticket_id):
        json_data = self.client.get_ticket(ticket_id)
        ticket, _ = self.update_or_create_instance(json_data)
        return ticket

    def fetch_delete_by_id(self, ticket_id):
        try:
            self.client.get_ticket(ticket_id)
        except api.ConnectWiseRecordNotFoundError:
            # This is what we expect to happen. Since it's gone in CW, we
            # are safe to delete it from here.
            models.Ticket.objects.filter(id=ticket_id).delete()
            logger.info(
                'Deleted ticket {} (if it existed).'.format(ticket_id)
            )

    def sync(self, reset=True):
        sync_job_qset = models.SyncJob.objects.filter(
            entity_name=self.model_class.__name__
        )

        if sync_job_qset.exists() and not reset:
            last_sync_job_time = sync_job_qset.last().start_time.isoformat()
            self.api_conditions.append(
                "lastUpdated > [{0}]".format(last_sync_job_time)
            )

        return super().sync(reset=reset)


class OpportunitySynchronizer(Synchronizer):
    """
    Coordinates retrieval and demarshalling of ConnectWise JSON
    Opportunity instances.
    """
    client_class = api.SalesAPIClient
    model_class = models.Opportunity
    related_meta = {
        'type': (models.OpportunityType, 'type'),
        'stage': (models.OpportunityStage, 'stage'),
        'status': (models.OpportunityStatus, 'status'),
        'primarySalesRep': (models.Member, 'primary_sales_rep'),
        'secondarySalesRep': (models.Member, 'secondary_sales_rep'),
        'company': (models.Company, 'company'),
        'closedBy': (models.Member, 'closed_by')
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.priority_map = {
            p.id: p for p in models.OpportunityPriority.objects.all()
        }

        self.stage_map = {
            s.id: s for s in models.OpportunityStage.objects.all()
        }

    def _instance_from_json(self, model_class, json_data, instance_map):
        instance = instance_map.get(json_data['id'])
        if not instance:
            instance = model_class()
            instance.id = json_data['id']
            instance.name = json_data['name']
            instance.save()
            instance_map[instance.id] = instance
        return instance

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']
        instance.notes = json_data['notes']
        instance.source = json_data['source']
        instance.location_id = json_data['locationId']
        instance.business_unit_id = json_data['businessUnitId']
        instance.customer_po = json_data['customerPO']

        # handle dates
        expected_close_date = json_data['expectedCloseDate']
        if expected_close_date:
            instance.expected_close_date = parse(expected_close_date).date()

        pipeline_change_date = json_data['pipelineChangeDate']
        if pipeline_change_date:
            instance.pipeline_change_date = parse(pipeline_change_date)

        date_became_lead = json_data['dateBecameLead']
        if date_became_lead:
            instance.date_became_lead = parse(date_became_lead)

        closed_date = json_data['closedDate']
        if closed_date:
            instance.closed_date = parse(closed_date)

        # handle foreign keys
        for json_field, value in self.related_meta.items():
            model_class, field_name = value
            self._assign_relation(instance,
                                  json_data,
                                  json_field,
                                  model_class,
                                  field_name)

        instance.priority = self._instance_from_json(
            models.OpportunityPriority,
            json_data['priority'],
            self.priority_map)

        instance.stage = self._instance_from_json(
            models.OpportunityStage,
            json_data['stage'],
            self.stage_map)

        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_opportunities(*args, **kwargs)

    # TODO - The implementation of these fetch methods ought
    # to be pushed up to the superclass, given that this pattern has emerged.
    def fetch_sync_by_id(self, instance_id):
        opportunity = self.client.by_id(instance_id)
        self.update_or_create_instance(opportunity)
        logger.info('Updated Opportunity {}'.format(opportunity))
        return opportunity

    def fetch_delete_by_id(self, instance_id):
        try:
            self.client.by_id(instance_id)
        except api.ConnectWiseRecordNotFoundError:
            # This is what we expect to happen. Since it's gone in CW, we
            # are safe to delete it from here.
            models.Opportunity.objects.filter(id=instance_id).delete()
            logger.info(
                'Deleted Opportunity {} (if it existed).'.format(instance_id)
            )


class OpportunityStatusSynchronizer(Synchronizer):
    """
    Coordinates retrieval and demarshalling of ConnectWise JSON
    OpportunityStatus instances.
    """
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
    """
    Coordinates retrieval and demarshalling of ConnectWise JSON
    OpportunityType instances.
    """
    client_class = api.SalesAPIClient
    model_class = models.OpportunityType

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.description = json_data['description']
        instance.inactive_flag = json_data['inactiveFlag']
        return instance

    def get_page(self, *args, **kwargs):
        return self.client.get_opportunity_types(*args, **kwargs)
