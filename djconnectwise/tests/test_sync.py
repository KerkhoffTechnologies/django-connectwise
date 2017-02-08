from copy import deepcopy
from unittest import TestCase

from djconnectwise.models import Company, ConnectWiseBoard, ConnectWiseBoardStatus
from djconnectwise.models import Member, ServiceTicket

from . import fixtures
from . import mocks
from .. import sync 


class TestCompanySynchronizer(TestCase):

    def setUp(self):
        self.synchronizer = sync.CompanySynchronizer()

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

    def test_sync(self):
        _, get_patch = mocks.company_api_get_call(fixtures.API_COMPANY_LIST)
        self.synchronizer.sync()
        company_dict = {c['id']: c for c in fixtures.API_COMPANY_LIST}

        for company in Company.objects.all():
            api_company = company_dict[company.id]
            self._assert_fields(company, api_company)

    def test_sync_update(self):
        identifier = 'Some New Company'
        api_company = deepcopy(fixtures.API_COMPANY)
        api_company['identifier'] = identifier
        api_company_list = [api_company]
        company_pre_update = Company.objects \
                                    .get(id=api_company['id'])
        _, get_patch = mocks.company_api_get_call(api_company_list)

        self.synchronizer.sync()
        company_post_update = Company.objects \
                                     .get(id=api_company['id'])

        self.assertNotEquals(company_pre_update.company_identifier,
                             identifier)
        self._assert_fields(company_post_update, api_company)


class TestBoardSynchronizer(TestCase):
    def setUp(self):
        self.synchronizer = sync.BoardSynchronizer()

    def test_sync(self):
        ConnectWiseBoard.objects.all().delete()
        mocks.service_api_get_boards_call(fixtures.API_BOARD_LIST)
        self.synchronizer.sync()

        local_boards = set(ConnectWiseBoard.objects.all()
                                                   .values_list('board_id', 'name'))

        api_boards = set([(s['id'], s['name']) for s in fixtures.API_BOARD_LIST])
        self.assertEquals(len(local_boards), len(api_boards))
        self.assertEquals(local_boards, api_boards)


class TestBoardStatusSynchronizer(TestCase):
    def setUp(self):
        self.synchronizer = sync.BoardStatusSynchronizer()

    def test_sync(self):
        ConnectWiseBoardStatus.objects.all().delete()
        mocks.service_api_get_statuses_call(fixtures.API_BOARD_STATUS_LIST)
        self.synchronizer.sync([b['id'] for b in fixtures.API_BOARD_LIST])

        local_statuses = set(ConnectWiseBoardStatus.objects
                                                   .all()
                                                   .values_list('id', 'status_name'))

        api_statuses = set([(s['id'], s['name']) for s in fixtures.API_BOARD_STATUS_LIST])
        self.assertEquals(len(local_statuses), len(api_statuses))
        self.assertEquals(local_statuses, api_statuses)


class TestServiceTicketSynchronizer(TestCase):

    def setUp(self):
        self.synchronizer = sync.ServiceTicketSynchronizer()

    def _get_local_and_api_ticket(self):
        api_ticket = self.synchronizer.service_client.get_tickets()[0]

        local_ticket, created = self.synchronizer.sync_ticket(api_ticket)
        return local_ticket, api_ticket

    def _sync_tickets(self):
        mocks.company_api_by_id_call(fixtures.API_COMPANY)
        mocks.service_api_tickets_call()

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

        mocks.service_api_update_ticket_call(api_service_ticket)
        mocks.service_api_get_ticket_call()

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
        self.synchronizer = sync.ServiceTicketSynchronizer()
        mocks.system_api_get_members_call([fixtures.API_MEMBER])

    def _assert_member_fields(self, local_member, api_member):
        self.assertEquals(local_member.first_name, api_member['firstName'])
        self.assertEquals(local_member.last_name, api_member['lastName'])
        self.assertEquals(local_member.office_email, api_member['officeEmail'])

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
