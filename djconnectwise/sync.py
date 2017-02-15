import logging

from dateutil.parser import parse

from djconnectwise.api import CompanyAPIClient
from djconnectwise.api import ServiceAPIClient
from djconnectwise.api import SystemAPIClient
from djconnectwise.models import Company
from djconnectwise.models import ConnectWiseBoard
from djconnectwise.models import ConnectWiseBoardStatus
from djconnectwise.models import Member
from djconnectwise.models import Project
from djconnectwise.models import ServiceTicket
from djconnectwise.models import ServiceTicketAssignment
from djconnectwise.models import SyncJob
from djconnectwise.models import TicketPriority
from djconnectwise.models import TicketStatus
from djconnectwise.utils import get_hash, get_filename_extension

from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import ContentFile
from django.utils import timezone

DEFAULT_AVATAR_EXTENSION = 'jpg'

logger = logging.getLogger(__name__)


class InvalidStatusError(Exception):
    pass


class CompanySynchronizer:
    """
    Coordinates retrieval and demarshalling of ConnectWise JSON
    Company instances.
    """

    def __init__(self, *args, **kwargs):
        self.client = CompanyAPIClient()
        self.companies = self.load_company_dict()

    def load_company_dict(self):
        """
        Returns a dict of all companies that reside locally
        """
        return {c.id: c for c in Company.objects.all()}

    def _assign_field_data(self, company, api_company):
        """
        Assigns field data from an api_company instance
        to a local Company model instance
        """
        company.company_name = api_company['name']
        company.company_identifier = api_company['identifier']
        company.phone_number = api_company['phoneNumber']
        company.fax_number = api_company['faxNumber']
        company.address_line1 = api_company['addressLine1']
        company.address_line2 = api_company['addressLine1']
        company.city = api_company['city']
        company.state_identifier = api_company['state']
        company.zip = api_company['zip']
        company.created = timezone.now()

    def sync(self):
        api_company_data = self.client.get()
        created_count = 0
        updated_count = 0
        deleted_count = 0

        for api_company in api_company_data:
            company_id = api_company['id']
            try:
                company = Company.objects.get(id=company_id)
                updated_count += 1
            except ObjectDoesNotExist:
                company = Company.objects.create(id=company_id)
                created_count += 1

            self._assign_field_data(company, api_company)
            company.save()

        return created_count, updated_count, deleted_count

    def get_or_create_company(self, company_id):
        """
        Creates and returns a Company instance if it does not already exist
        """
        # Assign company to ticket. Create a new company if it does not already
        # exist

        company = self.companies.get(company_id)
        if not company:
            # fetch company from api
            api_company = self.client.by_id(company_id)
            company = Company.objects.create(id=company_id)

            self._assign_field_data(company, api_company)
            company.save()
            logger.info('Company Created: {}'.format(company_id))
            self.companies[company.id] = company
        return company


class BoardSynchronizer:

    def __init__(self, *args, **kwargs):
        self.client = ServiceAPIClient()

    def sync(self):
        updated_count = 0
        created_count = 0
        deleted_count = 0

        for board in self.client.get_boards():
            _, created = ConnectWiseBoard.objects.update_or_create(
                board_id=board['id'],
                defaults={
                    'name': board['name'],
                    'inactive': board['inactive'],
                }
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        return created_count, updated_count, deleted_count


class BoardStatusSynchronizer:

    def __init__(self, *args, **kwargs):
        self.client = ServiceAPIClient()

    def _sync(self, board_ids):

        updated_count = 0
        created_count = 0
        deleted_count = 0

        for board_id in board_ids:
            # TODO - Django doesn't provide an efficient
            # way to bulk get or create. May need to
            # invest time in a more efficient approach
            for status in self.client.get_statuses(board_id):
                _, created = ConnectWiseBoardStatus.objects.update_or_create(
                    status_id=status['id'],
                    defaults={
                        'board_id': board_id,
                        'status_name': status['name'],
                    }
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

        return created_count, updated_count, deleted_count

    def sync(self, board_ids=None):

        if not board_ids:
            board_qs = ConnectWiseBoard.objects.all()
            board_ids = board_qs.values_list('board_id', flat=True)

        return self._sync(board_ids)


class PrioritySynchronizer:

    def __init__(self, *args, **kwargs):
        self.client = ServiceAPIClient()
        self.ticket_priority_map = {
            ticket.name: ticket for ticket in TicketPriority.objects.all()
        }

    def _assign_field_data(self, ticket_priority, api_priority):
        ticket_priority.name = api_priority['name']
        ticket_priority.priority_id = api_priority['id']
        ticket_priority.color = api_priority['color']
        ticket_priority.sort = api_priority['sort']
        return ticket_priority

    def get_or_create_ticket_priority(self, api_priority):
        """
        Gets or creates a TicketPriority instance for
        the supplied API Priority JSON structure
        """
        ticket_priority = self.ticket_priority_map.get(
            api_priority['name'])

        created = False
        if not ticket_priority:
            ticket_priority = TicketPriority()
            self._assign_field_data(ticket_priority, api_priority)
            ticket_priority.save()
            created = True

        return ticket_priority, created

    def update_or_create_ticket_priority(self, api_priority):
        """
        Creates and returns a TicketPriority instance if
        it does not already exist
        """
        ticket_priority, created = self.get_or_create_ticket_priority(
            api_priority)

        action = 'Created' if created else 'Updated'

        if not created:
            self._assign_field_data(ticket_priority, api_priority)
            ticket_priority.save()

        self.ticket_priority_map[ticket_priority.name] = ticket_priority

        msg = 'TicketPriority {}: {}'
        logger.info(msg.format(action, ticket_priority.name))

        return ticket_priority, created

    def sync(self):
        created_count = 0
        updated_count = 0
        deleted_count = 0

        for api_priority in self.client.get_priorities():
            _, created = self.update_or_create_ticket_priority(api_priority)

            if created:
                created_count += 1
            else:
                updated_count += 1

        return created_count, updated_count, deleted_count


class MemberSynchronizer:

    def __init__(self, *args, **kwargs):
        self.client = SystemAPIClient()
        self.last_sync_job = None

        sync_job_qset = SyncJob.objects.all()

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
            member_qset = Member.objects.filter(identifier=username)
            if member_qset.exists():
                member = member_qset.first()

                member.first_name = api_member['firstName']
                member.last_name = api_member['lastName']
                member.office_email = api_member['officeEmail']
                updated_count += 1
                logger.info('Update Member: {0}'.format(member.identifier))
            else:
                member = Member.create_member(api_member)
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
                self._save_avatar(member, avatar, attachment_filename)

            member.save()

        return created_count, updated_count, deleted_count


class ServiceTicketSynchronizer:
    """
    Coordinates retrieval and demarshalling of ConnectWise JSON
    objects to the local counterparts.
    """

    def __init__(self, reset=False):
        self.company_synchronizer = CompanySynchronizer()
        self.status_synchronizer = BoardStatusSynchronizer()
        self.priority_synchronizer = PrioritySynchronizer()

        self.reset = reset
        self.last_sync_job = None
        extra_conditions = ''
        sync_job_qset = SyncJob.objects.all()

        if sync_job_qset.exists() and not self.reset:
            self.last_sync_job = sync_job_qset.last()
            last_sync_job_time = self.last_sync_job.start_time.isoformat()
            extra_conditions = "lastUpdated > [{0}]".format(last_sync_job_time)

            log_msg = 'Preparing sync job for objects updated since {}.'
            logger.info(log_msg.format(last_sync_job_time))
            logger.info(
                'ServiceTicket Extra Conditions: {0}'.format(extra_conditions))
        else:
            logger.info('Preparing full ticket sync job.')
            # absence of a sync job indicates that this is an initial/full
            # sync, in which case we do not want to retrieve closed tickets
            extra_conditions = 'ClosedFlag = False'

        self.service_client = ServiceAPIClient(
            extra_conditions=extra_conditions)

        self.system_client = SystemAPIClient()

        # we need to remove the underscores to ensure an accurate
        # lookup of the normalized api fieldnames
        self.local_service_ticket_fields = self._create_field_lookup(
            ServiceTicket)
        self.local_company_fields = self._create_field_lookup(Company)

        self.ticket_status_map = {
            ticket.status_name: ticket for ticket in TicketStatus.objects.all()
        }

        self.members_map = {m.identifier: m for m in Member.objects.all()}
        self.project_map = {p.name: p for p in Project.objects.all()}
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

    def _manage_member_assignments(self, service_ticket):
        # reset board/ticket assignment in case the assigned resources have
        # changed since last sync
        member = None
        if service_ticket.resources:
            usernames = [u.strip()
                         for u in service_ticket.resources.split(',')]
            # clear existing assignments
            ServiceTicketAssignment.objects.filter(
                service_ticket=service_ticket).delete()
            for username in usernames:
                member = self.members_map.get(username)
                assignment = ServiceTicketAssignment()
                assignment.member = member
                assignment.service_ticket = service_ticket
                self.ticket_assignments[
                    (username, service_ticket.id,)] = assignment
                logger.info('Member ServiceTicket Assignment: %s - %s' %
                            (username, service_ticket.id))

    def get_or_create_project(self, api_ticket):
        api_project = api_ticket['project']
        if api_project:
            project = self.project_map.get(api_project['name'])
            if not project:
                project = Project()
                project.name = api_project['name']
                project.project_href = api_project['_info']['project_href']
                project.project_id = api_project['id']
                project.save()
                self.project_map[project.name] = project
                logger.info('Project Created: %s' % project.name)
            return project

    def get_or_create_ticket_status(self, api_ticket):
        """
        Creates and returns a TicketStatus instance if
        it does not already exist
        """
        api_status = api_ticket['status']
        status_name = api_status['name'].strip()
        ticket_status = self.ticket_status_map.get(status_name)

        if not ticket_status:
            kwargs = dict(
                status_id=api_status['id'],
                status_name=status_name
            )

            if TicketStatus.objects.filter(**kwargs).exists():
                ticket_status = TicketStatus.objects.get(**kwargs)
            else:
                logger.info('TicketStatus Created - %s' % status_name)
                ticket_status, created = TicketStatus.objects.get_or_create(
                    **kwargs)

            self.ticket_status_map[status_name] = ticket_status

        else:
            if ticket_status.status_id != api_status['id']:
                ticket_status.status_id = api_status['id']
                ticket_status.save()

        return ticket_status

    def sync_ticket(self, api_ticket):
        """
        Creates a new local instance of the supplied ConnectWise
        ServiceTicket instance.
        """
        api_ticket_id = api_ticket['id']
        service_ticket, created = ServiceTicket.objects \
                                               .get_or_create(pk=api_ticket_id)

        # if the status results in a move to a different column
        original_status = not created and service_ticket.status or None
        new_ticket_status = self.get_or_create_ticket_status(api_ticket)

        service_ticket.closed_flag = api_ticket['closedFlag']
        service_ticket.type = api_ticket['type']
        service_ticket.priority_text = api_ticket['priority']['name']
        service_ticket.location = api_ticket['serviceLocation']
        service_ticket.summary = api_ticket['summary']
        service_ticket.entered_date_utc = api_ticket['dateEntered']
        service_ticket.last_updated_utc = api_ticket['_info']['lastUpdated']
        service_ticket.resources = api_ticket['resources']
        service_ticket.budget_hours = api_ticket['budgetHours']
        service_ticket.actual_hours = api_ticket['actualHours']
        service_ticket.record_type = api_ticket['recordType']

        team = api_ticket['team']
        if team:
            service_ticket.team_id = api_ticket['team']['id']

        service_ticket.api_text = str(api_ticket)
        service_ticket.board_name = api_ticket['board']['name']
        service_ticket.board_id = api_ticket['board']['id']
        service_ticket.board_status_id = api_ticket['status']['id']

        company_id = api_ticket['company']['id']
        service_ticket.company = self.company_synchronizer \
                                     .get_or_create_company(company_id)

        priority, _ = self.priority_synchronizer \
            .get_or_create_ticket_priority(api_ticket['priority'])
        service_ticket.priority = priority

        service_ticket.status = new_ticket_status
        service_ticket.project = self.get_or_create_project(api_ticket)
        service_ticket.save()
        action = created and 'Created' or 'Updated'

        status_changed = ''
        if original_status != new_ticket_status:
            status_txt = 'Status Changed From: {} To: {}'
            status_changed = status_txt.format(original_status,
                                               new_ticket_status)

        log_info = '{} Ticket #: {} {}'
        logger.info(log_info.format(action, service_ticket.id, status_changed))

        self._manage_member_assignments(service_ticket)
        return service_ticket, created

    def update_api_ticket(self, service_ticket):
        """"
            Updates the state of a generic ticket
            and determines which api to send the updated ticket data to
        """
        api_service_ticket = self.service_client.get_ticket(service_ticket.id)

        if service_ticket.closed_flag:
            api_service_ticket['closedFlag'] = service_ticket.closed_flag
            ticket_status, created = TicketStatus.objects.get_or_create(
                status_name__iexact='Closed')
        else:
            ticket_status = service_ticket.status

        if not service_ticket.closed_flag:

            try:
                board_status = ConnectWiseBoardStatus.objects.get(
                    board_id=service_ticket.board_id,
                    status_name=ticket_status.status_name
                )
            except Exception as e:
                raise InvalidStatusError(e)

            api_service_ticket['status']['id'] = board_status.status_id

        # no need for a callback update when updating via api
        api_service_ticket['skipCallback'] = True
        logger.info('Update API Ticket Status: %s - %s' %
                    (service_ticket.id, api_service_ticket['status']['name']))

        return self.service_client.update_ticket(api_service_ticket)

    def close_ticket(self, service_ticket):
        """Closes the specified service ticket returns True if the
           if the close operation was successful on the connectwise server.
           Note: It appears that the connectwise server does not return a
           permissions error if user does not have access to this operation.
        """

        service_ticket.closed_flag = True
        service_ticket.save()
        logger.info('Close API Ticket: %s' % service_ticket.id)
        api_ticket = self.update_api_ticket(service_ticket)
        ticket_is_closed = api_ticket['closedFlag']

        if not ticket_is_closed:
            service_ticket.closed_flag = ticket_is_closed
            service_ticket.save()

        return ticket_is_closed

    def sync(self):
        """
        Synchronizes tickets between the ConnectWise server and the
        local database. Synchronization is performed in batches
        specified in the DJCONNECTWISE_API_BATCH_LIMIT setting
        """
        sync_job = SyncJob.objects.create()

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
        ServiceTicketAssignment.objects.bulk_create(
            list(self.ticket_assignments.values()))

        # now prune closed service tickets.
        logger.info('Deleting Closed Tickets')
        delete_qset = ServiceTicket.objects.filter(closed_flag=True)
        delete_count = delete_qset.count()
        delete_qset.delete()

        sync_job.end_time = timezone.now()
        sync_job.save()

        return created_count, updated_count, delete_count
