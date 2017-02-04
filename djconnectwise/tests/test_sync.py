import random
import time

from copy import deepcopy
from unittest import TestCase

from djconnectwise.models import Company, Member
from djconnectwise.models import ServiceTicket, TicketStatus

from . import fixtures
from .mocks import company_api_get_call
from ..sync import CompanySynchronizer, ServiceTicketSynchronizer


class TestCompanySynchronizer(TestCase):

    def setUp(self):
        self.synchronizer = CompanySynchronizer()

    def _assert_fields(self, company, api_company):
        assert company.company_name == api_company['name']
        assert company.company_identifier == api_company['identifier']
        assert company.phone_number == api_company['phoneNumber']
        assert company.fax_number == api_company['faxNumber']
        assert company.address_line1 == api_company['addressLine1']
        assert company.address_line2 == api_company['addressLine1']
        assert company.city == api_company['city']
        assert company.state_identifier == api_company['state']
        assert company.zip == api_company['zip']

    def test_sync_companies(self):
        _, get_patch = company_api_get_call(fixtures.API_COMPANY_LIST)
        self.synchronizer.sync_companies()
        company_dict = {c['id']: c for c in fixtures.API_COMPANY_LIST}

        for company in Company.objects.all():
            api_company = company_dict[company.id]
            self._assert_fields(company, api_company)

    def test_sync_companies_update(self):
        identifier = 'Some New Company'
        api_company = deepcopy(fixtures.API_COMPANY)
        api_company['identifier'] = identifier
        api_company_list = [api_company]
        company_pre_update = Company.objects \
                                    .get(id=api_company['id'])
        _, get_patch = company_api_get_call(api_company_list)

        self.synchronizer.sync_companies()
        company_post_update = Company.objects \
                                     .get(id=api_company['id'])

        self.assertNotEquals(company_pre_update.company_identifier,
                             identifier)
        self._assert_fields(company_post_update, api_company)


class TestServiceTicketSynchronizer(TestCase):

    def setUp(self):
        # setup.init()
        self.synchronizer = ServiceTicketSynchronizer()
        self.synchronizer.sync_tickets()

    def _get_local_and_api_ticket(self):
        api_ticket = self.synchronizer.service_client.get_tickets(
            page=random.randrange(1, 100, 2), page_size=1)[0]
        local_ticket, created = self.synchronizer.sync_ticket(api_ticket)
        return local_ticket, api_ticket

    def test_sync_tickets(self):
        num_tickets = self.synchronizer.service_client.tickets_count()

        start = time.time()
        created_count, updated_count, delete_count = self.synchronizer \
                                                         .sync_tickets()
        end = time.time()

        # sync took less than 60 seconds
        self.assertLess(end - start, 45)

        self.assertEqual(num_tickets, ServiceTicket.objects.all().count())

    def test_update_api_ticket(self):
        local_ticket, api_ticket = self._get_local_and_api_ticket()
        # find a new random status
        ticket_status_types = [s for s in TicketStatus.objects.all()]
        status_index = random.randrange(0, len(ticket_status_types), 1)

        local_ticket.status = ticket_status_types[status_index]
        local_ticket.save()
        self.synchronizer.update_api_ticket(local_ticket)
        updated_api_ticket = self.synchronizer.service_client.get_ticket(
            local_ticket.id)
        self.assertEqual(updated_api_ticket['status'][
                         'name'], local_ticket.status.status_name)

    def test_close_ticket(self):
        local_ticket, api_ticket = self._get_local_and_api_ticket()
        self.synchronizer.close_ticket(local_ticket)

        updated_api_ticket = self.synchronizer.service_client.get_ticket(
            local_ticket.id)
        self.assertTrue(updated_api_ticket['closedFlag'])


class TestMemberSynchronization(TestCase):

    def setUp(self):
        # setup.init()
        self.synchronizer = ServiceTicketSynchronizer()
        member = Member()
        member.identifier = 'some_member'
        member.first_name = 'Bob'
        member.last_name = 'Dobbs'
        member.office_email = 'bdobbs@example.ca'
        member.save()

    def test_sync_member(self):

        # get members list
        local_members = [m for m in list(self.synchronizer.members_map.keys())]
        members_json = self.synchronizer.system_client.get_members()
        api_members = []

        for member in members_json:
            if member['identifier'] not in local_members:
                api_members.append(member)

        if api_members:

            new_member = self.synchronizer.sync_member(
                api_members[0]['identifier'])
            user = new_member.user
            original_name = new_member.user.name
            user.name = 'some name'
            user.save()

            new_member = self.synchronizer.sync_member(
                api_members[0]['identifier'])

            # verify that the fields are syncing as expected
            self.assertEqual(new_member.user.name, original_name)

        else:
            raise ValueError('No members to test')
