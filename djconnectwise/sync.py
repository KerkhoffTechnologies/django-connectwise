import datetime
import logging
import uuid

from dateutil.parser import parse
from djconnectwise.api import CompanyAPIClient, ServiceAPIClient
from djconnectwise.api import SystemAPIClient
from djconnectwise.models import ServiceTicket, Company, ConnectWiseBoardStatus
from djconnectwise.models import SyncJob
from djconnectwise.models import TicketPriority, Member, Project
from djconnectwise.models import TicketStatus, ServiceTicketAssignment

from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import ContentFile
from django.utils import timezone


logger = logging.getLogger(__name__)


class InvalidStatusError(Exception):
    pass


class CompanySynchronizer:
    """
    Coordinates retrieval and demarshalling of ConnectWise JSON
    Company instances.
    """

    def __init__(self, *args, **kwargs):
        self.company_client = CompanyAPIClient()
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

    def sync_companies(self):
        api_company_data = self.company_client.get()
        created_count = 0
        updated_count = 0

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

        msg = 'Synced Companies - Created: {} , Updated: {}'.format(
            created_count, updated_count)

        logger.info('Synced Companies - Created: {} , Updated: {}'.format(
            created_count, updated_count))

        return created_count, updated_count, msg

    def get_or_create_company(self, company_id):
        """
        Creates and returns a Company instance if it does not already exist
        """
        # Assign company to ticket. Create a new company if it does not already
        # exist

        company = self.companies.get(company_id)
        if not company:
            # fetch company from api
            api_company = self.company_client.by_id(company_id)
            company = Company.objects.create(id=company_id)

            self._assign_field_data(company, api_company)
            company.save()
            logger.info('Company Created: {}'.format(company_id))
            self.companies[company.id] = company
        return company


class ServiceTicketSynchronizer:
    """
    Coordinates retrieval and demarshalling of ConnectWise JSON
    objects to the local counterparts.
    """

    def __init__(self, reset=False):

        self.company_synchronizer = CompanySynchronizer()
        self.reset = reset
        self.last_sync_job = None
        extra_conditions = ''
        sync_job_qset = SyncJob.objects.all()

        if sync_job_qset.exists() and not self.reset:
            self.last_sync_job = sync_job_qset.last()
            extra_conditions = "lastUpdated > [{0}]".format(
                self.last_sync_job.start_time.isoformat())
            logger.info(
                'ServiceTicket Extra Conditions: {0}'.format(extra_conditions))
        else:
            # absence of a sync job indicates that this is an initial/full
            # sync, in whichcase we do not want to retrieve closed tickets
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

        self.ticket_priority_map = {
            ticket.name: ticket for ticket in TicketPriority.objects.all()
        }

        self.members_map = {m.identifier: m for m in Member.objects.all()}
        self.project_map = {p.name: p for p in Project.objects.all()}
        self.ticket_assignments = {}
        self.updated_members = []

        self.exclude_fields = ('priority', 'status', 'company')

    def _create_field_lookup(self, clazz):
        field_map = [(f, f.replace('_', ''))
                     for f in clazz._meta.get_all_field_names()]
        return dict(field_map)

    def _normalize_keys(self, api_keys):
        """Returns a lookup dict of api keys in lower case format

        It is necessary to normalize the field names of the SOAP element
        in order to map field data to a local service ticket
        """
        return {key.lower(): key for key in api_keys}

    def _map_field_data(self, service_ticket, api_ticket):
        ticket_fields = list(self.local_service_ticket_fields.items())
        for local_field, local_lookup_key in ticket_fields:

            if local_field not in self.exclude_fields:
                if local_field in api_ticket:
                    api_field_value = api_ticket.get(local_field)

                    if api_field_value:
                        if isinstance(api_field_value, datetime.datetime):
                            api_field_value = timezone.make_aware(
                                api_field_value,
                                timezone.get_current_timezone())

                        setattr(service_ticket, local_field, api_field_value)

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

    def get_or_create_ticket_priority(self, api_ticket):
        """
        Creates and returns a TicketPriority instance if
        it does not already exist
        """
        ticket_priority = self.ticket_priority_map.get(
            api_ticket['priority']['name'])

        if not ticket_priority:
            ticket_priority = TicketPriority()
            ticket_priority.name = api_ticket['priority']['name']
            ticket_priority.save()
            self.ticket_priority_map[ticket_priority.name] = ticket_priority
            logger.info('TicketPriority Created: %s' % ticket_priority.name)

        return ticket_priority

    def sync_members(self):
        members_json = self.system_client.get_members()

        for api_member in members_json:
            username = api_member['identifier']
            member_qset = Member.objects.filter(identifier=username)
            if member_qset.exists():
                member = member_qset.first()

                member.first_name = api_member['firstName']
                member.last_name = api_member['lastName']
                member.office_email = api_member['officeEmail']

                logger.info('Update Member: {0}'.format(member.identifier))
            else:
                member = Member.create_member(api_member)
                logger.info('Create Member: {0}'.format(member.identifier))

            # only update the avatar if the member profile was updated since
            # last sync
            member_last_updated = parse(api_member['_info']['lastUpdated'])

            if self.last_sync_job:
                member_stale = member_last_updated > \
                    self.last_sync_job.start_time

                if not self.last_sync_job or member_stale:
                    member_img = self.system_client \
                                     .get_member_image_by_identifier(username)

                    img_name = '{}.jpg'.format(uuid.uuid4())
                    img_file = ContentFile(member_img)
                    member.avatar.save(img_name, img_file)

            member.save()
            self.members_map[member.identifier] = member

    def sync_ticket(self, api_ticket):
        """
        Creates a new local instance of the supplied
        ConnectWise SOAP ServiceTicket instance
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

        service_ticket.priority = self.get_or_create_ticket_priority(
            api_ticket)
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

    def sync_tickets(self):
        """
        Synchronizes tickets between the ConnectWise server and the
        local database. Synchronization is performed in batches
        specified in the DJCONNECTWISE_API_BATCH_LIMIT setting
        """
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
        logger.info('Deleting Closed Tickets')

        # now prune closed service tickets.
        delete_qset = ServiceTicket.objects.filter(closed_flag=True)
        delete_count = delete_qset.count()
        delete_qset.delete()

        sync_info = 'SYNC COMPLETE - CREATED: {} UPDATED {} DELETED: {}'
        logger.info(sync_info.format(created_count,
                                     updated_count, delete_count))
        return created_count, updated_count, delete_count

    def sync_board_statuses(self):
        board_ids = [board_id for board_id in ServiceTicket.objects.all(
        ).values_list('board_id', flat=True).distinct() if board_id]
        for board_id in board_ids:
            for status in self.service_client.get_statuses(board_id):
                ConnectWiseBoardStatus.objects.get_or_create(
                    board_id=board_id,
                    status_id=status['id'],
                    status_name=status['name']
                )

    def start(self):
        """
        Initiates the sync mechanism. Returns the number of tickets created
        """
        print("------------------------- 1 -------------------------------")
        self.sync_board_statuses()
        print("------------------------- 2 -------------------------------")
        self.sync_job = SyncJob.objects.create()
        print("------------------------- 3 -------------------------------")
        self.sync_members()
        print("------------------------- 4 -------------------------------")
        created_count, updated_count, delete_count = self.sync_tickets()
        print("------------------------- 5 -------------------------------")
        self.sync_board_statuses()
        print("------------------------- 6 -------------------------------")
        self.sync_job.end_time = timezone.now()
        print("------------------------- 7 -------------------------------")
        self.sync_job.save()

        return created_count, updated_count, delete_count
