import logging

from dateutil.parser import parse

from djconnectwise import api
from djconnectwise import models
from djconnectwise.utils import get_hash, get_filename_extension

from django.core.files.base import ContentFile
from django.utils import timezone

DEFAULT_AVATAR_EXTENSION = 'jpg'

logger = logging.getLogger(__name__)


class InvalidStatusError(Exception):
    pass


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
        Creates and returns an instance if
        it does not already exist
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


class BoardChildSynchronizer(Synchronizer):

    def _assign_field_data(self, instance, json_data):
        instance.id = json_data['id']
        instance.name = json_data['name']
        instance.board = models.ConnectWiseBoard.objects.get(
            id=json_data['boardId'])
        return instance

    def client_call(self, board_id):
        raise NotImplementedError

    def get_json(self):
        results_json = []
        board_qs = models.ConnectWiseBoard.objects.all()

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


class TeamSynchronizer(BoardChildSynchronizer):
    client_class = api.ServiceAPIClient
    model_class = models.Team

    def _assign_field_data(self, instance, json_data):
        instance = super(TeamSynchronizer, self)._assign_field_data(
            instance, json_data)

        members = list(models.Member.objects.filter(
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
        return instance

    def get_json(self):
        return self.client.get_projects()


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
            member_qset = models.Member.objects.filter(identifier=username)
            if member_qset.exists():
                member = member_qset.first()
                member.first_name = api_member['firstName']
                member.last_name = api_member['lastName']
                member.office_email = api_member['officeEmail']
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
                'Ticket Extra Conditions: {0}'.format(extra_conditions))
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

        self.status_map = {s.name: s for s in models.BoardStatus.objects.all()}

        self.members_map = {
            m.identifier: m for m in models.Member.objects.all()
        }
        self.project_map = {p.name: p for p in models.Project.objects.all()}
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
                    self.ticket_assignments[
                        (username, ticket.id,)] = assignment
                    msg = 'Member Ticket Assignment: {} - {}'
                    logger.info(msg.format(username, ticket.id))
                else:
                    logger.error(
                        'Failed to locate member with username {} for ticket '
                        '{} assignment.'.format(username, ticket.id)
                    )

    def get_or_create_project(self, api_ticket):
        api_project = api_ticket['project']
        if api_project:
            project = self.project_map.get(api_project['name'])
            if not project:
                project = models.Project()
                project.name = api_project['name']
                project.project_href = api_project['_info']['project_href']
                project.project_id = api_project['id']
                project.save()
                self.project_map[project.name] = project
                logger.info('Project Created: %s' % project.name)
            return project

    def get_or_create_ticket_status(self, api_ticket):
        """
        Creates and returns a BoardStatus instance if
        it does not already exist
        """
        api_status = api_ticket['status']
        name = api_status['name'].strip()
        ticket_status = self.status_map.get(name)
        created = False

        if not ticket_status:
            kwargs = dict(
                id=api_status['id'],
                name=name
            )

            if models.BoardStatus.objects.filter(**kwargs).exists():
                ticket_status = models.BoardStatus.objects.get(**kwargs)
            else:
                logger.info('BoardStatus Created - %s' % name)
                ticket_status, created = models.BoardStatus.objects \
                    .get_or_create(**kwargs)

            self.status_map[name] = ticket_status

        else:
            if ticket_status.id != api_status['id']:
                ticket_status.id = api_status['id']
                ticket_status.save()

        return ticket_status, created

    def sync_ticket(self, json_data):
        """
        Creates a new local instance of the supplied ConnectWise
        Ticket instance.
        """
        json_data_id = json_data['id']
        ticket, created = models.Ticket.objects \
            .get_or_create(pk=json_data_id)

        # if the status results in a move to a different column
        original_status = not created and ticket.status or None

        ticket.closed_flag = json_data['closedFlag']
        ticket.type = json_data['type']
        ticket.priority_text = json_data['priority']['name']
        ticket.summary = json_data['summary']
        ticket.entered_date_utc = json_data['dateEntered']
        ticket.last_updated_utc = json_data['_info']['lastUpdated']
        ticket.resources = json_data['resources']
        ticket.budget_hours = json_data['budgetHours']
        ticket.actual_hours = json_data['actualHours']
        ticket.record_type = json_data['recordType']

        team = json_data['team']
        if team:
            ticket.team_id = json_data['team']['id']

        ticket.api_text = str(json_data)

        ticket.board = models.ConnectWiseBoard.objects.get(
            pk=json_data['board']['id'])

        ticket.company, _ = self.company_synchronizer \
            .get_or_create_instance(json_data['company'])

        priority, _ = self.priority_synchronizer \
            .get_or_create_instance(json_data['priority'])

        ticket.priority = priority

        try:
            location = models.Location.objects.get(
                id=json_data['locationId'])
            ticket.location = location
        except:
            pass

        # TODO - Discuss - Do we assume that the status exists
        # or do we want to do a roundtrip and retrieve from the server?
        new_ticket_status = models.BoardStatus.objects.get(
            pk=json_data['status']['id'])

        ticket.status = new_ticket_status

        ticket.project = self.get_or_create_project(json_data)
        ticket.save()
        action = created and 'Created' or 'Updated'

        status_changed = ''
        if original_status != new_ticket_status:
            status_txt = 'Status Changed From: {} To: {}'
            status_changed = status_txt.format(original_status,
                                               new_ticket_status)

        log_info = '{} Ticket #: {} {}'
        logger.info(log_info.format(action, ticket.id, status_changed))

        self._manage_member_assignments(ticket)
        return ticket, created

    def update_json_data(self, ticket):
        """"
        Updates the state of a generic ticket and determines which api
        to send the updated ticket data to.
        """
        json_data = self.service_client.get_ticket(ticket.id)

        if ticket.closed_flag:
            json_data['closedFlag'] = ticket.closed_flag
            ticket_status = models.BoardStatus.objects.get(
                closed_status=True)
        else:
            ticket_status = ticket.status

        if not ticket.closed_flag:
            try:
                board_status = models.BoardStatus.objects.get(
                    board_id=ticket.board_id,
                    name=ticket_status.name
                )
            except models.BoardStatus.DoesNotExist as e:
                raise InvalidStatusError(e)

            json_data['status']['id'] = board_status.id

        # no need for a callback update when updating via api
        json_data['skipCallback'] = True
        logger.info(
            'Update API Ticket Status: {} - {}'.format(
                ticket.id, json_data['status']['name']
            )
        )

        return self.service_client.update_ticket(json_data)

    def close_ticket(self, ticket):
        """
        Closes the specified service ticket returns True if the close
        operation was successful on the connectwise server.
        Note: It appears that the connectwise server does not return a
        permissions error if user does not have access to this operation.
        """
        ticket.closed_flag = True
        ticket.save()
        logger.info('Close API Ticket: %s' % ticket.id)
        api_ticket = self.update_api_ticket(ticket)
        ticket_is_closed = api_ticket['closedFlag']

        if not ticket_is_closed:
            ticket.closed_flag = ticket_is_closed
            ticket.save()

        return ticket_is_closed

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

        page = 0
        accumulated = 0

        logger.info('Synchronization Started')

        while True:
            logger.info('Processing Batch #: {}'.format(page))
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

        logger.info('Saving Ticket Assignments')
        models.TicketAssignment.objects.bulk_create(
            list(self.ticket_assignments.values()))

        # now prune closed service tickets.
        logger.info('Deleting Closed Tickets')
        delete_qset = models.Ticket.objects.filter(closed_flag=True)
        delete_count = delete_qset.count()
        delete_qset.delete()

        sync_job.end_time = timezone.now()
        sync_job.save()

        return created_count, updated_count, delete_count


class TicketUpdater(object):
    """Send ticket updates to ConnectWise."""

    def __init__(self):
        self.service_client = api.ServiceAPIClient()

    def update_api_ticket(self, ticket):
        api_ticket = self.service_client.get_ticket(ticket.id)

        if ticket.closed_flag:
            api_ticket['closedFlag'] = ticket.closed_flag
            ticket_status = models.BoardStatus.objects.get(
                closed_status=True)
        else:
            ticket_status = ticket.status

        if not ticket.closed_flag:
            # Ensure that the new status is valid for the CW board.
            try:
                cw_board = models.ConnectWiseBoard.objects.get(
                    id=ticket.board_id)
                board_status = models.BoardStatus.objects.get(
                    board_id=ticket.board_id,
                    name=ticket_status.name
                )
                api_ticket['status']['id'] = board_status.id
            except models.ConnectWiseBoard.DoesNotExist:
                raise InvalidStatusError("Failed to find the ticket's board.")
            except models.BoardStatus.DoesNotExist:
                raise InvalidStatusError(
                    "{} is not a valid status for the ticket's "
                    "ConnectWise board ({}).".
                    format(
                        ticket_status.name,
                        cw_board.name
                    )
                )

        # No need for a callback update when updating via api
        api_ticket['skipCallback'] = True
        logger.info(
            'Update API Ticket Status: {} - {}'.format(
                ticket.id, api_ticket['status']['name']
            )
        )

        return self.service_client.update_ticket(api_ticket)

    def close_ticket(self, ticket):
        """
        Closes the specified service ticket returns True if the close
        operation was successful on the connectwise server.
        Note: It appears that the connectwise server does not return a
        permissions error if user does not have access to this operation.
        """
        ticket.closed_flag = True
        ticket.save()
        logger.info('Close API Ticket: %s' % ticket.id)
        api_ticket = self.update_api_ticket(ticket)
        ticket_is_closed = api_ticket['closedFlag']

        if not ticket_is_closed:
            ticket.closed_flag = ticket_is_closed
            ticket.save()

        return ticket_is_closed
