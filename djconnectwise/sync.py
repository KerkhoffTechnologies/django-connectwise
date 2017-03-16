import logging

from dateutil.parser import parse

from djconnectwise import api
from djconnectwise import models
from djconnectwise.utils import get_hash, get_filename_extension

from django.core.files.base import ContentFile
from django.utils import timezone

DEFAULT_AVATAR_EXTENSION = 'jpg'

logger = logging.getLogger(__name__)


class Synchronizer:
    lookup_key = 'id'

    def __init__(self, *args, **kwargs):
        self.instance_map = {}
        self.client = self.client_class()

        self.load_instance_map()

    def load_instance_map(self):
        qset = self.get_queryset()
        self.instance_map = {
            getattr(i, self.lookup_key): i for i in qset
        }

    def get_queryset(self):
        return self.model_class.objects.all()

    def get_json(self):
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

        self.instance_map[self.lookup_key] = instance

        msg = ' {}: {} {}'
        logger.info(msg.format(action, self.model_class.__name__, instance))

        return instance, created

    def sync(self):
        created_count = 0
        updated_count = 0
        deleted_count = 0

        for json_data in self.get_json():
            _, created = self.update_or_create_instance(json_data)

            if created:
                created_count += 1
            else:
                updated_count += 1

        return created_count, updated_count, deleted_count


class BoardSynchronizer(Synchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.ConnectWiseBoard

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']
        instance.inactive = json_data['inactive']
        return instance

    def get_json(self):
        return self.client.get_boards()

    def get_queryset(self):
        return self.model_class.all_objects.all()


class BoardChildSynchronizer(Synchronizer):

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']
        instance.board = models.ConnectWiseBoard.all_objects.get(
            id=json_data['boardId'])
        return instance

    def client_call(self, board_id):
        raise NotImplementedError

    def get_json(self):
        results_json = []
        board_qs = models.ConnectWiseBoard.all_objects.all()

        for board_id in board_qs.values_list('id', flat=True):
            results_json += self.client_call(board_id)

        return results_json


class BoardStatusSynchronizer(BoardChildSynchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.BoardStatus

    def _assign_field_data(self, instance, json_data):
        instance = super(BoardStatusSynchronizer, self)._assign_field_data(
            instance, json_data)

        instance.sort_order = json_data['sortOrder']
        instance.display_on_board = json_data['displayOnBoard']
        instance.inactive = json_data['inactive']
        instance.closed_status = json_data['closedStatus']

        return instance

    def client_call(self, board_id):
        return self.client.get_statuses(board_id)

    def get_queryset(self):
        return self.model_class.all_objects.all()


class TeamSynchronizer(BoardChildSynchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.Team

    def _assign_field_data(self, instance, json_data):
        instance = super(TeamSynchronizer, self)._assign_field_data(
            instance, json_data)

        members = []
        if json_data['members']:
            members = list(models.Member.all_objects.filter(
                id__in=json_data['members']))

        instance.save()

        instance.members.clear()
        instance.members.add(*members)
        return instance

    def client_call(self, board_id):
        return self.client.get_teams(board_id)


class CompanySynchronizer(Synchronizer):
    """
    Coordinates retrieval and demarshalling of ConnectWise JSON
    Company instances.
    """
    client_class = api.CompanyAPIClient
    model_class = models.Company

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
        return company

    def get_json(self):
        return self.client.get()


class LocationSynchronizer(Synchronizer):
    """
    Coordinates retrieval and demarshalling of ConnectWise JSON
    Company instances.
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
        location.where = location_json['where']
        return location

    def get_json(self):
        return self.client.get_locations()


class PrioritySynchronizer(Synchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.TicketPriority
    lookup_key = 'name'

    def _assign_field_data(self, ticket_priority, api_priority):
        ticket_priority.name = api_priority['name']
        ticket_priority.id = api_priority['id']
        ticket_priority.color = api_priority.get('color')

        # work around due to api data inconsistencies
        sort_value = api_priority.get('sort') or api_priority.get('sortOrder')
        if sort_value:
            ticket_priority.sort = sort_value

        return ticket_priority

    def get_json(self):
        return self.client.get_priorities()


class ProjectSynchronizer(Synchronizer):
    client_class = api.ProjectAPIClient
    model_class = models.Project

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']
        instance.project_href = json_data['_info'].get('project_href')
        instance.status_name = json_data['status']['name']
        return instance

    def get_json(self):
        return self.client.get_projects()

    def get_queryset(self):
        return self.model_class.all_objects.all()


class MemberSynchronizer:

    def __init__(self, *args, **kwargs):
        self.client = api.SystemAPIClient()
        self.last_sync_job = None

        sync_job_qset = models.SyncJob.objects.all()

        if sync_job_qset.exists():
            self.last_sync_job = sync_job_qset.last()

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

    def sync(self):
        members_json = self.client.get_members()

        updated_count = 0
        created_count = 0
        deleted_count = 0

        for api_member in members_json:
            username = api_member['identifier']
            member_qset = models.Member.all_objects.filter(identifier=username)
            if member_qset.exists():
                member = member_qset.first()
                member.first_name = api_member['firstName']
                member.last_name = api_member['lastName']
                member.office_email = api_member['officeEmail']
                member.license_class = api_member['licenseClass']
                updated_count += 1
                logger.info('Update Member: {0}'.format(member.identifier))
            else:
                member = models.Member.create_member(api_member)
                created_count += 1
                logger.info('Create Member: {0}'.format(member.identifier))

            # only update the avatar if the member profile
            # was updated since last sync
            member_last_updated = parse(api_member['_info']['lastUpdated'])
            member_stale = False

            if self.last_sync_job:
                member_stale = member_last_updated > \
                    self.last_sync_job.start_time

            if not self.last_sync_job or member_stale:
                (attachment_filename, avatar) = self.client \
                    .get_member_image_by_identifier(username)
                if attachment_filename and avatar:
                    self._save_avatar(member, avatar, attachment_filename)

            member.save()

        return created_count, updated_count, deleted_count


class TicketSynchronizer:
    """
    Coordinates retrieval and demarshalling of ConnectWise JSON
    objects to the local counterparts.
    """

    def __init__(self, reset=False):
        self.company_synchronizer = CompanySynchronizer()
        self.status_synchronizer = BoardStatusSynchronizer()
        self.priority_synchronizer = PrioritySynchronizer()
        self.location_synchronizer = LocationSynchronizer()

        self.reset = reset
        self.last_sync_job = None
        extra_conditions = ''
        sync_job_qset = models.SyncJob.objects.all()

        if sync_job_qset.exists() and not self.reset:
            self.last_sync_job = sync_job_qset.last()
            last_sync_job_time = self.last_sync_job.start_time.isoformat()
            extra_conditions = "lastUpdated > [{0}]".format(last_sync_job_time)

            log_msg = 'Preparing sync job for objects updated since {}.'
            logger.info(log_msg.format(last_sync_job_time))
            logger.info(
                'Ticket extra conditions: {0}'.format(extra_conditions))
        else:
            logger.info('Preparing full ticket sync job.')
            # absence of a sync job indicates that this is an initial/full
            # sync, in which case we do not want to retrieve closed tickets
            extra_conditions = 'ClosedFlag = False'

        self.service_client = api.ServiceAPIClient(
            extra_conditions=extra_conditions)

        self.system_client = api.SystemAPIClient()

        # we need to remove the underscores to ensure an accurate
        # lookup of the normalized api fieldnames
        self.local_ticket_fields = self._create_field_lookup(
            models.Ticket)
        self.local_company_fields = self._create_field_lookup(models.Company)

        self.members_map = {
            m.identifier: m for m in models.Member.all_objects.all()
        }
        self.project_map = {p.id: p for p in models.Project.all_objects.all()}
        self.ticket_assignments = {}
        self.updated_members = []

        self.exclude_fields = ('priority', 'status', 'company')

    def _create_field_lookup(self, clazz):
        field_map = [
            (f.name, f.name.replace('_', '')) for
            f in clazz._meta.get_fields(
                include_parents=False, include_hidden=True)
        ]
        return dict(field_map)

    def _manage_member_assignments(self, ticket):
        # reset board/ticket assignment in case the assigned resources have
        # changed since last sync
        member = None
        if ticket.resources:
            usernames = [u.strip()
                         for u in ticket.resources.split(',')]
            # clear existing assignments
            models.TicketAssignment.objects.filter(
                ticket=ticket).delete()
            for username in usernames:
                member = self.members_map.get(username)

                if member:
                    assignment = models.TicketAssignment()
                    assignment.member = member
                    assignment.ticket = ticket
                    self.ticket_assignments[(username, ticket.id,)] = \
                        assignment
                    msg = 'Member ticket assignment: ' \
                          'ticket {}, member {}'.format(ticket.id, username)
                    logger.info(msg)
                else:
                    logger.error(
                        'Failed to locate member with username {} for ticket '
                        '{} assignment.'.format(username, ticket.id)
                    )

    def get_or_create_project(self, api_project):
        if api_project:
            project = self.project_map.get(api_project['id'])
            if not project:
                project = models.Project()
                project.id = api_project['id']
                project.name = api_project['name']
                project.project_href = api_project['_info']['project_href']
                project.project_id = api_project['id']
                project.save()
                self.project_map[project.id] = project
                logger.info('Project created: %s' % project.name)
            return project

    def sync_ticket(self, json_data):
        """
        Creates a new local instance of the supplied ConnectWise
        Ticket instance.
        """
        json_data_id = json_data['id']
        logger.info('Syncing ticket {}'.format(json_data_id))
        ticket, created = models.Ticket.objects \
            .get_or_create(pk=json_data_id)

        # if the status results in a move to a different column
        original_status = not created and ticket.status or None

        ticket.closed_flag = json_data['closedFlag']
        ticket.type = json_data['type']
        ticket.summary = json_data['summary']
        ticket.entered_date_utc = json_data['dateEntered']
        ticket.last_updated_utc = json_data['_info']['lastUpdated']
        ticket.required_date_utc = json_data['requiredDate']
        ticket.resources = json_data['resources']
        ticket.budget_hours = json_data['budgetHours']
        ticket.actual_hours = json_data['actualHours']
        ticket.record_type = json_data['recordType']

        team = json_data['team']
        try:
            if team:
                ticket.team = models.Team.objects.get(
                    pk=team['id'])
        except models.Team.DoesNotExist:
            logger.warning(
                'Failed to find team {} for ticket {}.'.format(
                    team['id'],
                    json_data_id
                )
            )

        ticket.api_text = str(json_data)

        try:
            ticket.board = models.ConnectWiseBoard.all_objects.get(
                pk=json_data['board']['id'])
        except models.ConnectWiseBoard.DoesNotExist:
            logger.warning(
                'Failed to find board {} for ticket {}.'.format(
                    json_data['board']['id'],
                    json_data_id
                )
            )

        ticket.company, _ = self.company_synchronizer \
            .get_or_create_instance(json_data['company'])

        priority, _ = self.priority_synchronizer \
            .get_or_create_instance(json_data['priority'])

        ticket.priority = priority

        try:
            location = models.Location.objects.get(
                id=json_data['locationId'])
            ticket.location = location
        except models.Location.DoesNotExist:
            logger.warning(
                'Failed to find location {} for ticket {}.'.format(
                    json_data['locationId'],
                    json_data_id
                )
            )

        new_ticket_status = None
        try:
            # TODO - Discuss - Do we assume that the status exists
            # or do we want to do a roundtrip and retrieve from the server?
            new_ticket_status = models.BoardStatus.all_objects.get(
                pk=json_data['status']['id'])
        except models.BoardStatus.DoesNotExist:
            logger.warning(
                'Failed to find board status {} for ticket {}.'.format(
                    json_data['status']['id'],
                    json_data_id
                )
            )

        ticket.status = new_ticket_status

        ticket.project = self.get_or_create_project(json_data['project'])
        ticket.save()
        action = created and 'Created' or 'Updated'

        status_changed = ''
        if original_status != new_ticket_status:
            status_changed = '; status changed from ' \
                         '{} to {}'.format(original_status, new_ticket_status)

        log_info = '{} ticket {}{}'.format(
            action, ticket.id, status_changed
        )
        logger.info(log_info)

        self._manage_member_assignments(ticket)
        return ticket, created

    def sync(self):
        """
        Synchronizes tickets between the ConnectWise server and the
        local database. Synchronization is performed in batches
        specified in the DJCONNECTWISE_API_BATCH_LIMIT setting
        """
        sync_job = models.SyncJob.objects.create()

        created_count = 0
        updated_count = 0
        ticket_ids = []

        page = 1  # Page is 1-indexed, not 0-indexed
        accumulated = 0

        logger.info('Synchronization started')

        while True:
            logger.info('Processing batch {}'.format(page))
            tickets = self.service_client.get_tickets(page=page)
            num_tickets = len(tickets)

            for ticket in tickets:
                ticket, created = self.sync_ticket(ticket)
                ticket_ids.append(ticket.id)

                if created:
                    created_count += 1
                else:
                    updated_count += 1

            page += 1
            accumulated += len(tickets)

            if not num_tickets:
                break

        if self.ticket_assignments:
            logger.info('Saving ticket assignments')
            models.TicketAssignment.objects.bulk_create(
                list(self.ticket_assignments.values()))

        # Now prune closed service tickets.
        logger.info('Deleting closed tickets')
        delete_qset = models.Ticket.objects.filter(closed_flag=True)
        delete_count = delete_qset.count()
        delete_qset.delete()

        sync_job.end_time = timezone.now()
        sync_job.save()

        return created_count, updated_count, delete_count
