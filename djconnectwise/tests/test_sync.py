from copy import deepcopy
from unittest import TestCase
import os

from djconnectwise.models import Company, Member
from djconnectwise.models import ServiceTicket

from . import fixtures
from .mocks import company_api_get_call, company_api_by_id_call
from .mocks import service_api_tickets_call, service_api_update_ticket_call
from .mocks import system_api_get_members_call, system_api_get_member_image_by_identifier_call, \
    service_api_get_ticket_call, get_member_avatar, CW_MEMBER_IMAGE_FILENAME
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

        self.assertNotEqual(company_pre_update.company_identifier,
                            identifier)
        self._assert_fields(company_post_update, api_company)


class TestServiceTicketSynchronizer(TestCase):

    def setUp(self):
        self.synchronizer = ServiceTicketSynchronizer()

    def _get_local_and_api_ticket(self):
        api_ticket = self.synchronizer.service_client.get_tickets()[0]

        local_ticket, created = self.synchronizer.sync_ticket(api_ticket)
        return local_ticket, api_ticket

    def _sync_tickets(self):
        company_api_by_id_call(fixtures.API_COMPANY)
        service_api_tickets_call()

        return self.synchronizer.sync_tickets()

    def test_sync_tickets(self):
        created_count, _, _ = self._sync_tickets()
        self.assertEqual(created_count, 1)

    def test_update_api_ticket(self):
        ServiceTicket.objects.all().delete()
        self._sync_tickets()

        board_name = 'Some Board Name'
        api_service_ticket = deepcopy(fixtures.API_SERVICE_TICKET)
        api_service_ticket['board']['name'] = board_name

        service_api_update_ticket_call(api_service_ticket)
        service_api_get_ticket_call()

        local_ticket = ServiceTicket.objects.first()
        local_ticket.board_name = board_name
        local_ticket.closed_flag = True
        local_ticket.save()

        updated_api_ticket = self.synchronizer.update_api_ticket(local_ticket)

        self.assertEqual(updated_api_ticket['board'][
                         'name'], local_ticket.board_name)


class TestMemberSynchronization(TestCase):

    def setUp(self):
        self.member_id = 'User1'
        self.synchronizer = ServiceTicketSynchronizer()
        system_api_get_members_call([fixtures.API_MEMBER])
        system_api_get_member_image_by_identifier_call((CW_MEMBER_IMAGE_FILENAME, get_member_avatar()))

    def _assert_member_fields(self, local_member, api_member):
        self.assertEqual(local_member.first_name, api_member['firstName'])
        self.assertEqual(local_member.last_name, api_member['lastName'])
        self.assertEqual(local_member.office_email, api_member['officeEmail'])

    def _clear_members(self):
        Member.objects.all().delete()

    def test_sync_member_update(self):
        self._clear_members()
        member = Member()
        member.identifier = self.member_id
        member.first_name = 'some stale first name'
        member.last_name = 'some stale last name'
        member.office_email = 'some@stale.com'
        member.save()

        self.synchronizer.sync_members()
        local_member = Member.objects.get(identifier=self.member_id)
        api_member = fixtures.API_MEMBER
        self._assert_member_fields(local_member, api_member)

    def test_sync_member_create(self):
        self._clear_members()
        self.synchronizer.sync_members()
        local_member = Member.objects.all().first()
        api_member = fixtures.API_MEMBER
        self._assert_member_fields(local_member, api_member)
