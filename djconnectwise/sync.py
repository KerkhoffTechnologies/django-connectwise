import datetime
import logging
import uuid

from dateutil.parser import parse

from django.core.files.base import ContentFile
from django.conf import settings
from django.utils import timezone


from djconnectwise.api import CompanyAPIRestClient, ServiceAPIRestClient, SystemAPIClient
from djconnectwise.models import (ServiceTicket, Company, ConnectWiseBoardStatus,
    TicketStatus, ServiceTicketAssignment)
from djconnectwise.models import TicketPriority, Member, ServiceProvider, Project

from djconnectwise.models import SyncJob

log = logging.getLogger('sync')


class InvalidStatusError(Exception):
    pass


class ServiceTicketSynchronizer(object):
    """
    Coordinates retrieval and demarshalling of ConnectWise JSON objects to the local counterparts.
    """
    def __init__(self, reset=False):
        self.reset = reset
        self.last_sync_job = None
        extra_conditions = ''
        sync_job_qset = SyncJob.objects.all()

        if sync_job_qset.exists() and not self.reset:
            self.last_sync_job = sync_job_qset.last()
            extra_conditions = "lastUpdated > [{0}]".format(self.last_sync_job.start_time.isoformat())
            log.info('ServiceTicket Extra Conditions: {0}'.format(extra_conditions))
        else:
            # absence of a sync job indicates that this is an initial/full sync, in which
            # case we do not want to retrieve closed tickets
            extra_conditions = 'ClosedFlag = False'

        self.service_client = ServiceAPIRestClient(extra_conditions=extra_conditions)
        self.company_client = CompanyAPIRestClient()
        self.system_client = SystemAPIClient()
        self.service_provider = self.load_service_provider()

        # we need to remove the underscores to ensure an accurate
        # lookup of the normalized api fieldnames
        self.local_service_ticket_fields = self._create_field_lookup(ServiceTicket)
        self.local_company_fields = self._create_field_lookup(Company)

        self.companies = {c.id: c for c in Company.objects.all()}
        self.ticket_status_map = {ticket.status_name: ticket for ticket in TicketStatus.objects.all()}
        self.ticket_priority_map = {ticket.title: ticket for ticket in TicketPriority.objects.all()}
        self.members_map = {m.user.username:m for m in Member.objects.all()}
        self.project_map = {p.name:p for p in Project.objects.all()}
        self.ticket_assignments = {}
        self.updated_members = []

        self.exclude_fields = ('priority','status', 'company')

    def _create_field_lookup(self, clazz):
        return dict([(f, f.replace('_', ''))for f in clazz._meta.get_all_field_names()])

    def _normalize_keys(self, api_keys):
        """Returns a lookup dict of api keys in lower case format

        It is necessary to normalize the field names of the SOAP element
        in order to map field data to a local service ticket
        """
        return {key.lower(): key for key in api_keys}

    def _map_field_data(self, service_ticket, api_ticket):

        for local_field, local_lookup_key in list(self.local_service_ticket_fields.items()):

            if local_field not in self.exclude_fields:
                if local_field in api_ticket:
                    api_field_value = api_ticket.get(local_field)

                    if api_field_value:
                        if isinstance(api_field_value, datetime.datetime):
                            api_field_value = timezone.make_aware(api_field_value, timezone.get_current_timezone())

                        setattr(service_ticket, local_field, api_field_value)


    def _manage_member_assignments(self, service_ticket):
        # reset board/ticket assignment in case the assigned resources have changed since last sync
        service_ticket.ticket_boards.clear()
        member = None
        if service_ticket.resources:
            usernames = [u.strip() for u in service_ticket.resources.split(',')]
            # clear existing assignments
            ServiceTicketAssignment.objects.filter(service_ticket=service_ticket).delete()
            for username in usernames:
                member = self.members_map.get(username)
                assignment = ServiceTicketAssignment()
                assignment.member = member
                assignment.service_ticket = service_ticket
                self.ticket_assignments[(username, service_ticket.id,)] = assignment
                log.info('Member ServiceTicket Assignment: %s - %s' % (username, service_ticket.id))

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
                log.info('Project Created: %s'%project.name)
            return project

    def get_or_create_ticket_status(self, api_ticket):
        """
        Creates and returns a TicketStatus instance if it does not already exist
        """
        api_status = api_ticket['status']
        status_name = api_status['name'].strip()
        ticket_status = self.ticket_status_map.get(status_name)

        if not ticket_status:
            kwargs = dict(
                status_id = api_status['id'],
                status_name = status_name
            )

            if TicketStatus.objects.filter(**kwargs).exists():
                ticket_status = TicketStatus.objects.get(**kwargs)
            else:
                log.info('TicketStatus Created - %s'%status_name)
                ticket_status, created = TicketStatus.objects.get_or_create(**kwargs)

            self.ticket_status_map[status_name] = ticket_status


        else:
            if ticket_status.status_id != api_status['id']:
                ticket_status.status_id = api_status['id']
                ticket_status.save()

        return ticket_status

    def get_or_create_ticket_priority(self, api_ticket):
        """
        Creates and returns a TicketPriority instance if it does not already exist
        """
        ticket_priority = self.ticket_priority_map.get(api_ticket['priority']['name'])
        if not ticket_priority:
            ticket_priority = TicketPriority()
            ticket_priority.title = api_ticket['priority']['name']
            ticket_priority.save()
            self.ticket_priority_map[ticket_priority.title] = ticket_priority
            log.info('TicketPriority Created: %s'%ticket_priority.title)
        return ticket_priority

    def get_or_create_company(self, company_id):
        """
        Creates and returns a Company instance if it does not already exist
        """
        # Assign company to ticket. Create a new company if it does not already exist

        company = self.companies.get(company_id)
        if not company:
            # fetch company from api
            api_company = self.company_client.get_company_by_id(company_id)
            company = Company.objects.create(id=company_id)

            company.company_name = api_company['name']
            company.company_identifier = api_company['identifier']
            company.phone_number =  api_company['phoneNumber']
            company.fax_number = api_company['faxNumber']
            company.address_line1 = api_company['addressLine1']
            company.address_line2 = api_company['addressLine1']
            company.city = api_company['city']
            company.state_identifier = api_company['state']
            company.zip = api_company['zip']
            company.created = timezone.now()
            company.save()
            log.info('Company Created: %s'%company_id)
            self.companies[company.id] = company
        return company

    def sync_members(self):
        members_json = self.system_client.get_members()

        for api_member in members_json:
            username = api_member['identifier']
            member_qset = Member.objects.filter(user__username=username)
            if member_qset.exists():
                member = member_qset.first()
                log.info('Update Member: {0}'.format(member.user.username))
            else:
                member = Member.create_member(
                    username,
                    settings.MEMBER_DEFAULT_PASSWORD,
                    self.service_provider
                )
                log.info('Create Member: {0}'.format(member.user.username))

            # only update the avatar if the member profile was updated since last sync

            member_last_updated = parse(api_member['_info']['lastUpdated'])

            if not self.last_sync_job or member_last_updated > self.last_sync_job.start_time:
                api_member_image = self.system_client.get_member_image_by_identifier(username)
                member.avatar.save('%s.jpg'%(uuid.uuid4(),), ContentFile(api_member_image))
                pass

            user = member.user
            user.name = api_member['firstName'] + ' ' + api_member['lastName']
            name_tokens = user.name.split(' ')
            if name_tokens:
                user.first_name = name_tokens[0]
                user.last_name = ' '.join(name_tokens[1:])

            user.email = api_member['officeEmail']
            user.active = not api_member['inactiveFlag']
            user.save()
            member.save()
            self.members_map[member.user.username] = member

    def sync_ticket(self, api_ticket, service_provider):
        """
        Creates a new local instance of the supplied ConnectWise SOAP ServiceTicket instance
        NOTE:
        """
        service_ticket, created = ServiceTicket.objects.get_or_create(pk=api_ticket['id'])

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

        service_ticket.company = self.get_or_create_company(api_ticket['company']['id'])
        service_ticket.priority = self.get_or_create_ticket_priority(api_ticket)
        service_ticket.provider = service_provider
        service_ticket.status = new_ticket_status
        service_ticket.project = self.get_or_create_project(api_ticket)
        service_ticket.save()
        action = created and 'Created' or 'Updated'

        # TODO: send a signal to be caught by what was once _manage_ticket_rank

        status_changed = ''
        if original_status != new_ticket_status:
            status_changed = 'Status Changed From: %s To: %s'%(original_status, new_ticket_status)

        log.info('%s Ticket #: %d %s'%(action, service_ticket.id, status_changed))

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
            ticket_status, created = TicketStatus.objects.get_or_create(status_name__iexact='Closed')
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
        log.info('Update API Ticket Status: %s - %s'%(service_ticket.id, api_service_ticket['status']['name'] ))

        return self.service_client.update_ticket(api_service_ticket).json()

    def load_service_provider(self):
        provider_qs = ServiceProvider.objects.all()
        if not provider_qs.exists():
            provider = ServiceProvider()
            provider.title = 'KTI'
            provider.save()
        else:
            provider = provider_qs.first()

        return provider

    def close_ticket(self, service_ticket):
        """Closes the specified service ticket returns True if the
           if the close operation was successful on the connectwise server.
           Note: It appears that the connectwise server does not return a
           permissions error if the user does not have access to this operation.
        """

        service_ticket.closed_flag = True
        service_ticket.save()
        log.info('Close API Ticket: %s'%service_ticket.id)
        api_ticket = self.update_api_ticket(service_ticket)
        ticket_is_closed = api_ticket['closedFlag']

        if not ticket_is_closed:
            service_ticket.closed_flag = ticket_is_closed
            service_ticket.save()

        return ticket_is_closed

    def sync_tickets(self):
        """
        Synchronizes tickets between the ConnectWise server and the local database.
        Synchronization is performed in batches specified in the
        DJCONNECTWISE_API_BATCH_LIMIT setting
        """
        created_count = 0
        updated_count = 0
        ticket_ids = []
        limit = settings.DJCONNECTWISE_API_BATCH_LIMIT  # TODO: this seems to be unused
        page = 0
        service_ticket_count = self.service_client.tickets_count()
        accumulated = 0

        log.info('Synchronization Started')

        while True:
            log.info('Processing Batch #: %s' % page)
            tickets = self.service_client.get_tickets(page=page)
            num_tickets = len(tickets)
            for ticket in tickets:
                ticket, created = self.sync_ticket(ticket, self.service_provider)
                ticket_ids.append(ticket.id)

                if created:
                    created_count += 1
                else:
                    updated_count += 1
            page += 1
            accumulated += len(tickets)

            if not num_tickets:
                break

        log.info('Saving Ticket Assignments')
        ServiceTicketAssignment.objects.bulk_create(list(self.ticket_assignments.values()))
        log.info('Deleting Closed Tickets')

        # now prune closed service tickets.
        delete_qset = ServiceTicket.objects.filter(closed_flag=True)
        delete_count = delete_qset.count()
        delete_qset.delete()

        log.info('Synchronization Complete - CREATED: %s UPDATED %s DELETED: %s'%(created_count,updated_count,delete_count))
        return created_count,updated_count,delete_count

    def sync_board_statuses(self):
        board_ids = [board_id for board_id in ServiceTicket.objects.all().values_list('board_id', flat=True).distinct() if board_id]
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
        print("------------------------------- 1 -------------------------------------")
        self.sync_board_statuses()
        print("------------------------------- 2 -------------------------------------")
        self.sync_job = SyncJob.objects.create()
        print("------------------------------- 3 -------------------------------------")
        self.sync_members()
        print("------------------------------- 4 -------------------------------------")
        created_count, updated_count, delete_count = self.sync_tickets()
        print("------------------------------- 5 -------------------------------------")
        self.sync_board_statuses()
        print("------------------------------- 6 -------------------------------------")
        self.sync_job.end_time = timezone.now()
        print("------------------------------- 7 -------------------------------------")
        self.sync_job.save()

        return created_count, updated_count, delete_count
