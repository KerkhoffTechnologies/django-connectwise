from copy import deepcopy
from unittest import TestCase

from djconnectwise.models import Company, CompanyStatus
from djconnectwise.models import ConnectWiseBoard
from djconnectwise.models import BoardStatus
from djconnectwise.models import Location
from djconnectwise.models import Team
from djconnectwise.models import Project
from djconnectwise.models import Ticket
from djconnectwise.models import TicketPriority
from djconnectwise.models import Member

from . import fixtures
from . import fixture_utils
from . import mocks
from .. import sync


class SynchronizerTestMixin:
    synchronizer_class = None
    model_class = None
    fixture = None

    def call_api(self, return_data):
        raise NotImplementedError

    def _assert_fields(self, instance, json_data):
        raise NotImplementedError

    def _clean(self):
        self.model_class.objects.all().delete()

    def _sync(self, return_data):
        _, get_patch = self.call_api(return_data)
        self.synchronizer = self.synchronizer_class()
        self._clean()
        self.synchronizer.sync()
        return _, get_patch

    def test_sync(self):
        instance_dict = {c['id']: c for c in self.fixture}

        for instance in self.model_class.objects.all():
            json_data = instance_dict[instance.id]
            self._assert_fields(instance, json_data)

    def test_sync_update(self):
        self._clean()
        self._sync(self.fixture)

        json_data = self.fixture[0]

        instance_id = json_data['id']
        original = self.model_class.objects \
            .get(id=instance_id)

        name = 'Some New Name'
        new_json = deepcopy(self.fixture[0])
        new_json['name'] = name
        new_json_list = [new_json]

        self._sync(new_json_list)

        changed = self.model_class.objects.get(id=instance_id)
        self.assertNotEqual(original.name,
                            name)
        self._assert_fields(changed, new_json)


class TestCompanySynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.CompanySynchronizer
    model_class = Company
    fixture = fixtures.API_COMPANY_LIST

    def setUp(self):
        mocks.company_api_get_company_statuses_call(
            fixtures.API_COMPANY_STATUS_LIST)
        sync.CompanyStatusSynchronizer().sync()

    def call_api(self, return_data):
        return mocks.company_api_get_call(return_data)

    def _assert_fields(self, company, api_company):
        self.assertEqual(company.name, api_company['name'])
        self.assertEqual(company.identifier, api_company['identifier'])
        self.assertEqual(company.phone_number, api_company['phoneNumber'])
        self.assertEqual(company.fax_number, api_company['faxNumber'])
        self.assertEqual(company.address_line1, api_company['addressLine1'])
        self.assertEqual(company.address_line2, api_company['addressLine1'])
        self.assertEqual(company.city, api_company['city'])
        self.assertEqual(company.state_identifier, api_company['state'])
        self.assertEqual(company.zip, api_company['zip'])
        self.assertEqual(company.status.id, api_company['status']['id'])


class TestProjectSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.ProjectSynchronizer
    model_class = Project
    fixture = fixtures.API_PROJECT_LIST

    def call_api(self, return_data):
        return mocks.project_api_get_projects_call(return_data)

    def _assert_fields(self, instance, json_data):
        assert instance.name == json_data['name']
        assert instance.id == json_data['id']


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
        ids = set([t.id for t in team.members.all()])
        self.assertEqual(team.id, team_json['id'])
        self.assertEqual(team.name, team_json['name'])
        self.assertEqual(team.board.id, team_json['boardId'])
        self.assertTrue(ids < set(team_json['members']))

    def test_sync(self):
        team_dict = {t['id']: t for t in fixtures.API_SERVICE_TEAM_LIST}
        self._sync(fixtures.API_SERVICE_TEAM_LIST)

        teams = list(Team.objects.all())
        self.assertEqual(len(teams), len(team_dict))
        for team in Team.objects.all():
            team_json = team_dict[team.id]
            self._assert_fields(team, team_json)

    def test_sync_update(self):
        self._clean()
        self._sync(fixtures.API_SERVICE_TEAM_LIST)

        api_team = fixtures.API_SERVICE_TEAM_LIST[0]
        id = api_team['id']
        team_pre_update = Team.objects \
            .get(id=id)

        name = 'Some New Name'
        api_team = deepcopy(api_team)
        api_team['name'] = name
        api_team_list = [api_team]
        self._sync(api_team_list)

        team_post_update = Team.objects \
            .get(id=id)

        self.assertNotEqual(team_pre_update.name,
                            name)
        self._assert_fields(team_post_update, api_team)


class TestPrioritySynchronizer(TestCase):

    def setUp(self):
        self.synchronizer = sync.PrioritySynchronizer()
        self.valid_prio_colors = \
            list(TicketPriority.DEFAULT_COLORS.values()) + \
            [TicketPriority.DEFAULT_COLOR]

    def _assert_fields(self, priority, api_priority):
        assert priority.name == api_priority['name']
        assert priority.id == api_priority['id']
        if 'color' in api_priority.keys():
            assert priority.color == api_priority['color']
        else:
            assert priority.color in self.valid_prio_colors
        if 'sortOrder' in api_priority.keys():
            assert priority.sort == api_priority['sortOrder']
        else:
            assert priority.sort is None

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
            api_priority = priority_dict[priority.id]
            self._assert_fields(priority, api_priority)

    def test_sync_update(self):
        self._clean()
        self._sync(fixtures.API_SERVICE_PRIORITY_LIST)
        id = fixtures.API_SERVICE_PRIORITY['id']
        priority_pre_update = TicketPriority.objects \
            .get(id=id)

        color = 'green'
        updated_api_priority = deepcopy(fixtures.API_SERVICE_PRIORITY)
        updated_api_priority['color'] = color

        self._sync([updated_api_priority])

        priority_post_update = TicketPriority.objects \
            .get(id=updated_api_priority['id'])

        self.assertNotEqual(priority_pre_update.color,
                            color)
        self._assert_fields(priority_post_update, updated_api_priority)


class TestCompanyStatusSynchronizer(TestCase):

    def setUp(self):
        self.synchronizer = sync.CompanyStatusSynchronizer()

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.name, json_data['name'])
        self.assertEqual(instance.default_flag, json_data['defaultFlag'])
        self.assertEqual(instance.inactive_flag, json_data['inactiveFlag'])
        self.assertEqual(instance.notify_flag, json_data['notifyFlag'])
        self.assertEqual(instance.dissalow_saving_flag,
                         json_data['disallowSavingFlag'])
        self.assertEqual(instance.notification_message,
                         json_data['notificationMessage'])
        self.assertEqual(instance.custom_note_flag,
                         json_data['customNoteFlag'])
        self.assertEqual(instance.cancel_open_tracks_flag,
                         json_data['cancelOpenTracksFlag'])

    def _clean(self):
        CompanyStatus.objects.all().delete()

    def _sync(self, return_value):
        _, get_patch = mocks.company_api_get_company_statuses_call(
            return_value)

        self.synchronizer.sync()

    def test_sync(self):
        self._clean()
        self._sync(fixtures.API_COMPANY_STATUS_LIST)
        instances = fixtures.API_COMPANY_STATUS_LIST
        instance_dict = {i['id']: i for i in instances}

        status_instances = CompanyStatus.objects.all()
        self.assertGreater(status_instances.count(), 0)
        for instance in status_instances:
            json_data = instance_dict[instance.id]
            self._assert_fields(instance, json_data)

    def test_sync_update(self):
        self._clean()
        self._sync(fixtures.API_COMPANY_STATUS_LIST)
        id = fixtures.API_COMPANY_STATUS['id']
        original_instance = CompanyStatus.objects \
            .get(id=id)

        name = 'some-name'
        json_data = deepcopy(fixtures.API_COMPANY_STATUS)
        json_data['name'] = name

        self._sync([json_data])

        updated_instance = CompanyStatus.objects \
            .get(id=json_data['id'])

        self.assertNotEqual(original_instance.name,
                            name)
        self._assert_fields(updated_instance, json_data)


class TestLocationSynchronizer(TestCase):

    def setUp(self):
        self.synchronizer = sync.LocationSynchronizer()

    def _assert_fields(self, location, api_location):
        assert location.name == api_location['name']
        assert location.id == api_location['id']
        assert location.where == api_location['where']

    def _clean(self):
        Location.objects.all().delete()

    def _sync(self, return_value):
        _, get_patch = mocks.service_api_get_locations_call(
            return_value)

        self.synchronizer.sync()

    def test_sync(self):
        self._clean()
        self._sync(fixtures.API_SERVICE_LOCATION_LIST)
        instances = fixtures.API_SERVICE_LOCATION_LIST
        instance_dict = {i['id']: i for i in instances}

        for instance in Location.objects.all():
            json_data = instance_dict[instance.id]
            self._assert_fields(instance, json_data)

    def test_sync_update(self):
        self._clean()
        self._sync(fixtures.API_SERVICE_LOCATION_LIST)
        id = fixtures.API_SERVICE_LOCATION['id']
        original_instance = Location.objects \
            .get(id=id)

        where = 'some-where'
        json_data = deepcopy(fixtures.API_SERVICE_LOCATION)
        json_data['where'] = where

        self._sync([json_data])

        updated_instance = Location.objects \
            .get(id=json_data['id'])

        self.assertNotEqual(original_instance.where,
                            where)
        self._assert_fields(updated_instance, json_data)


class TestBoardSynchronizer(TestCase):

    def setUp(self):
        self.synchronizer = sync.BoardSynchronizer()

    def _sync(self):
        return fixture_utils.init_boards()

    def _local_board_set(self):
        board_qs = ConnectWiseBoard.objects.all()
        return set(board_qs.values_list('id', 'name'))

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
        self._clean()
        fixture_utils.init_boards()

    def _board_ids(self, board_status_list):
        return [b['id'] for b in board_status_list]

    def _clean(self):
        BoardStatus.objects.all().delete()

    def _sync(self):
        self._clean()
        mocks.service_api_get_statuses_call(fixtures.API_BOARD_STATUS_LIST)
        return self.synchronizer.sync()

    def _assert_sync(self, board_status_list):
        status_qs = BoardStatus.objects.all()
        local_statuses = set(status_qs.values_list('id', 'name'))
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
        created_count, updated_count, _ = self.synchronizer.sync()

        self.assertEqual(created_count, 0)
        self.assertEqual(updated_count, len(fixtures.API_BOARD_STATUS_LIST))
        self._assert_sync(updated_statuses)

    def test_sync(self):
        created_count, updated_count, _ = self._sync()
        self.assertEqual(created_count, len(fixtures.API_BOARD_STATUS_LIST))
        self.assertEqual(updated_count, 0)
        self._assert_sync(fixtures.API_BOARD_STATUS_LIST)


class TestTicketSynchronizer(TestCase):

    def setUp(self):
        self.synchronizer = sync.TicketSynchronizer()
        fixture_utils.init_board_statuses()

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


class TestMemberSynchronization(TestCase):

    def setUp(self):
        self.identifier = 'User1'
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
        member.id = 176
        member.identifier = self.identifier
        member.first_name = 'some stale first name'
        member.last_name = 'some stale last name'
        member.office_email = 'some@stale.com'
        member.save()

        self.synchronizer.sync()
        local_member = Member.objects.get(identifier=self.identifier)
        api_member = fixtures.API_MEMBER
        self._assert_member_fields(local_member, api_member)

    def test_sync_member_create(self):
        self._clear_members()
        self.synchronizer.sync()
        local_member = Member.objects.all().first()
        api_member = fixtures.API_MEMBER
        self._assert_member_fields(local_member, api_member)


class TestTicketSynchronization(TestCase):

    def _init_tickets(self):
        Ticket.objects.all().delete()
        fixture_utils.init_boards()
        fixture_utils.init_board_statuses()
        fixture_utils.init_teams()
        fixture_utils.init_tickets()

    def _test_delete_ticket(self, fixture):
        """Local ticket should be deleted if omitted from sync"""
        ticket_id = fixtures.API_SERVICE_TICKET['id']
        ticket_qset = Ticket.objects.filter(id=ticket_id)
        self._init_tickets()
        self.assertEqual(ticket_qset.count(), 1)
        method_name = 'djconnectwise.api.ServiceAPIClient.get_tickets'
        mocks.create_mock_call(method_name, fixture)

        synchronizer = sync.TicketSynchronizer()
        synchronizer.sync()
        self.assertEqual(ticket_qset.count(), 0)

    def test_delete_ticket(self):
        self._test_delete_ticket([])

    def test_delete_closed_ticket(self):
        """Local ticket should be deleted if omitted from sync"""
        ticket_fixture = deepcopy(fixtures.API_SERVICE_TICKET)
        ticket_fixture['closedFlag'] = True
        self._test_delete_ticket([ticket_fixture])
