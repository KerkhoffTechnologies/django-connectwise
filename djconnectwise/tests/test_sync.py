from copy import deepcopy
from unittest import TestCase

from djconnectwise.models import Company
from djconnectwise.models import ConnectWiseBoard
from djconnectwise.models import ConnectWiseBoardStatus
from djconnectwise.models import Team
from djconnectwise.models import TicketPriority
from djconnectwise.models import Member
from djconnectwise.models import ServiceTicket

from . import fixtures
from . import fixture_utils
from . import mocks
from .. import sync


class TestCompanySynchronizer(TestCase):

    def setUp(self):
        self.synchronizer = sync.CompanySynchronizer()
        self._clean()

    def _clean(self):
        Company.objects.all().delete()

    def _sync(self, return_data):
        _, get_patch = mocks.company_api_get_call(return_data)
        self.synchronizer.sync()
        return _, get_patch

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
        company_dict = {c['id']: c for c in fixtures.API_COMPANY_LIST}

        for company in Company.objects.all():
            api_company = company_dict[company.company_id]
            self._assert_fields(company, api_company)

    def test_sync_update(self):
        self._clean()
        self._sync(fixtures.API_COMPANY_LIST)

        api_company = fixtures.API_COMPANY
        company_id = api_company['id']
        company_pre_update = Company.objects \
            .get(company_id=company_id)

        name = 'Some New Company Name'
        api_company = deepcopy(fixtures.API_COMPANY)
        api_company['name'] = name
        api_company_list = [api_company]
        self._sync(api_company_list)

        company_post_update = Company.objects \
                                     .get(company_id=company_id)

        self.assertNotEqual(company_pre_update.company_name,
                            name)
        self._assert_fields(company_post_update, api_company)


class TestTeamSynchronizer(TestCase):

    def setUp(self):
        self.synchronizer = sync.TeamSynchronizer()
        self._clean()
        fixture_utils.init_boards()

    def _clean(self):
        Team.objects.all().delete()

    def _sync(self, return_data):
        _, get_patch = mocks.service_api_get_teams_call(return_data)
        self.synchronizer.sync()
        return _, get_patch

    def _assert_fields(self, team, team_json):
        member_ids = set([t.member_id for t in team.members.all()])
        self.assertEquals(team.team_id, team_json['id'])
        self.assertEquals(team.name, team_json['name'])
        self.assertEquals(team.board.board_id, team_json['boardId'])
        self.assertTrue(member_ids < set(team_json['members']))

    def test_sync(self):
        team_dict = {t['id']: t for t in fixtures.API_SERVICE_TEAM_LIST}
        self._sync(fixtures.API_SERVICE_TEAM_LIST)

        teams = list(Team.objects.all())
        self.assertEquals(len(teams), len(team_dict))
        for team in Team.objects.all():
            team_json = team_dict[team.team_id]
            self._assert_fields(team, team_json)

    def test_sync_update(self):
        self._clean()
        self._sync(fixtures.API_SERVICE_TEAM_LIST)

        api_team = fixtures.API_SERVICE_TEAM_LIST[0]
        team_id = api_team['id']
        team_pre_update = Team.objects \
            .get(team_id=team_id)

        name = 'Some New Name'
        api_team = deepcopy(api_team)
        api_team['name'] = name
        api_team_list = [api_team]
        self._sync(api_team_list)

        team_post_update = Team.objects \
            .get(team_id=team_id)

        self.assertNotEqual(team_pre_update.name,
                            name)
        self._assert_fields(team_post_update, api_team)


class TestPrioritySynchronizer(TestCase):

    def setUp(self):
        self.synchronizer = sync.PrioritySynchronizer()

    def _assert_fields(self, priority, api_priority):
        assert priority.name == api_priority['name']
        assert priority.priority_id == api_priority['id']
        assert priority.color == api_priority['color']
        assert priority.sort == api_priority['sortOrder']

    def _clean(self):
        TicketPriority.objects.all().delete()

    def _sync(self, return_value):
        _, get_patch = mocks.service_api_get_priorities_call(
            return_value)

        self.synchronizer.sync()

    def test_sync(self):
        self._clean()
        self._sync(fixtures.API_SERVICE_PRIORITY_LIST)
        priorities = fixtures.API_SERVICE_PRIORITY_LIST
        priority_dict = {p['id']: p for p in priorities}

        for priority in TicketPriority.objects.all():
            api_priority = priority_dict[priority.priority_id]
            self._assert_fields(priority, api_priority)

    def test_sync_update(self):
        self._clean()
        self._sync(fixtures.API_SERVICE_PRIORITY_LIST)
        priority_id = fixtures.API_SERVICE_PRIORITY['id']
        priority_pre_update = TicketPriority.objects \
            .get(priority_id=priority_id)

        color = 'green'
        updated_api_priority = deepcopy(fixtures.API_SERVICE_PRIORITY)
        updated_api_priority['color'] = color

        self._sync([updated_api_priority])

        priority_post_update = TicketPriority.objects \
            .get(priority_id=updated_api_priority['id'])

        self.assertNotEqual(priority_pre_update.color,
                            color)
        self._assert_fields(priority_post_update, updated_api_priority)


class TestBoardSynchronizer(TestCase):

    def setUp(self):
        self.synchronizer = sync.BoardSynchronizer()

    def _sync(self):
        ConnectWiseBoard.objects.all().delete()
        mocks.service_api_get_boards_call(fixtures.API_BOARD_LIST)
        return self.synchronizer.sync()

    def _local_board_set(self):
        board_qs = ConnectWiseBoard.objects.all()
        return set(board_qs.values_list('board_id', 'name'))

    def _api_board_set(self, board_data):
        return set([(s['id'], s['name']) for s in board_data])

    def test_sync(self):
        created_count, updated_count, _ = self._sync()
        local_boards = self._local_board_set()
        api_boards = self._api_board_set(fixtures.API_BOARD_LIST)

        self.assertEqual(local_boards, api_boards)
        self.assertEqual(updated_count, 0)
        self.assertEqual(created_count, len(fixtures.API_BOARD_LIST))

    def test_sync_update(self):
        self._sync()
        updated_boards = deepcopy(fixtures.API_BOARD_LIST)
        updated_boards[0]['name'] = 'New Board Name'
        mocks.service_api_get_boards_call(updated_boards)
        created_count, updated_count, _ = self.synchronizer.sync()

        local_boards = self._local_board_set()
        api_boards = self._api_board_set(updated_boards)

        self.assertEqual(local_boards, api_boards)
        self.assertEqual(updated_count, len(fixtures.API_BOARD_LIST))
        self.assertEqual(created_count, 0)


class TestBoardStatusSynchronizer(TestCase):

    def setUp(self):
        self.synchronizer = sync.BoardStatusSynchronizer()

    def _board_ids(self, board_status_list):
        return [b['id'] for b in board_status_list]

    def _sync(self):
        ConnectWiseBoardStatus.objects.all().delete()
        mocks.service_api_get_statuses_call(fixtures.API_BOARD_STATUS_LIST)
        board_ids = self._board_ids(fixtures.API_BOARD_LIST)
        return self.synchronizer.sync(board_ids)

    def _assert_sync(self, board_status_list):
        status_qs = ConnectWiseBoardStatus.objects.all()
        local_statuses = set(status_qs.values_list('status_id', 'status_name'))
        api_statuses = set([(s['id'], s['name'])
                            for s in board_status_list])
        num_local_statuses = len(local_statuses)

        self.assertEqual(num_local_statuses, len(api_statuses))
        self.assertEqual(local_statuses, api_statuses)

    def test_sync_updated(self):
        self._sync()
        updated_statuses = deepcopy(fixtures.API_BOARD_STATUS_LIST)
        updated_statuses[0]['name'] = 'New Status Name'
        mocks.service_api_get_statuses_call(updated_statuses)

        board_ids = self._board_ids(fixtures.API_BOARD_LIST)

        created_count, updated_count, _ = self.synchronizer.sync(board_ids)

        self.assertEqual(created_count, 0)
        self.assertEqual(updated_count, len(fixtures.API_BOARD_STATUS_LIST))
        self._assert_sync(updated_statuses)

    def test_sync(self):
        created_count, updated_count, _ = self._sync()
        self.assertEqual(created_count, len(fixtures.API_BOARD_STATUS_LIST))
        self.assertEqual(updated_count, 0)
        self._assert_sync(fixtures.API_BOARD_STATUS_LIST)


class TestServiceTicketSynchronizer(TestCase):

    def setUp(self):
        self.synchronizer = sync.ServiceTicketSynchronizer()

    def _get_local_and_api_ticket(self):
        api_ticket = self.synchronizer.service_client.get_tickets()[0]

        local_ticket, created = self.synchronizer.sync_ticket(api_ticket)
        return local_ticket, api_ticket

    def _sync(self):
        mocks.company_api_by_id_call(fixtures.API_COMPANY)
        mocks.service_api_tickets_call()

        return self.synchronizer.sync()

    def test_sync(self):
        created_count, _, _ = self._sync()
        self.assertEqual(created_count, 1)

    def test_update_api_ticket(self):
        ServiceTicket.objects.all().delete()
        self._sync()

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
        self.member_identifier = 'User1'
        self.synchronizer = sync.MemberSynchronizer()
        mocks.system_api_get_members_call([fixtures.API_MEMBER])
        mocks.system_api_get_member_image_by_identifier_call(
            (mocks.CW_MEMBER_IMAGE_FILENAME, mocks.get_member_avatar()))

    def _assert_member_fields(self, local_member, api_member):
        self.assertEqual(local_member.first_name, api_member['firstName'])
        self.assertEqual(local_member.last_name, api_member['lastName'])
        self.assertEqual(local_member.office_email, api_member['officeEmail'])

    def _clear_members(self):
        Member.objects.all().delete()

    def test_sync_member_update(self):
        self._clear_members()
        member = Member()
        member.member_id = 176
        member.identifier = self.member_identifier
        member.first_name = 'some stale first name'
        member.last_name = 'some stale last name'
        member.office_email = 'some@stale.com'
        member.save()

        self.synchronizer.sync()
        local_member = Member.objects.get(identifier=self.member_identifier)
        api_member = fixtures.API_MEMBER
        self._assert_member_fields(local_member, api_member)

    def test_sync_member_create(self):
        self._clear_members()
        self.synchronizer.sync()
        local_member = Member.objects.all().first()
        api_member = fixtures.API_MEMBER
        self._assert_member_fields(local_member, api_member)
