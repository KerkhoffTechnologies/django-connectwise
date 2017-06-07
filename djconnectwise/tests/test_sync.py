from copy import deepcopy
from unittest import TestCase

from dateutil.parser import parse
from django.conf import settings
from djconnectwise.models import BoardStatus
from djconnectwise.models import Company, CompanyStatus
from djconnectwise.models import ConnectWiseBoard
from djconnectwise.models import Location
from djconnectwise.models import Member
from djconnectwise.models import Opportunity
from djconnectwise.models import OpportunityStatus
from djconnectwise.models import OpportunityType
from djconnectwise.models import Project
from djconnectwise.models import SyncJob
from djconnectwise.models import Team
from djconnectwise.models import Ticket
from djconnectwise.models import TicketPriority

from . import fixtures
from . import fixture_utils
from . import mocks
from .. import sync
from ..sync import log_sync_job


def assert_sync_job(model_class):
    qset = SyncJob.objects.filter(entity_name=model_class.__name__)
    assert qset.exists()


class SynchronizerTestMixin:
    synchronizer_class = None
    model_class = None
    fixture = None

    def call_api(self, return_data):
        raise NotImplementedError

    def _assert_fields(self, instance, json_data):
        raise NotImplementedError

    def _sync(self, return_data):
        _, get_patch = self.call_api(return_data)
        self.synchronizer = self.synchronizer_class()
        self.synchronizer.sync()
        return _, get_patch

    def test_sync(self):
        self._sync(self.fixture)
        instance_dict = {c['id']: c for c in self.fixture}

        for instance in self.model_class.objects.all():
            json_data = instance_dict[instance.id]
            self._assert_fields(instance, json_data)

        assert_sync_job(self.model_class)

    def test_sync_update(self):
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


class TestTeamSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.TeamSynchronizer
    model_class = Team
    fixture = fixtures.API_SERVICE_TEAM_LIST

    def call_api(self, return_data):
        return mocks.service_api_get_teams_call(return_data)

    def setUp(self):
        fixture_utils.init_boards()

    def _assert_fields(self, team, team_json):
        ids = set([t.id for t in team.members.all()])
        self.assertEqual(team.id, team_json['id'])
        self.assertEqual(team.name, team_json['name'])
        self.assertEqual(team.board.id, team_json['boardId'])
        self.assertTrue(ids < set(team_json['members']))


class TestPrioritySynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.PrioritySynchronizer
    model_class = TicketPriority
    fixture = fixtures.API_SERVICE_PRIORITY_LIST

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

    def setUp(self):
        self.synchronizer = sync.PrioritySynchronizer()
        self.valid_prio_colors = \
            list(TicketPriority.DEFAULT_COLORS.values()) + \
            [TicketPriority.DEFAULT_COLOR]

    def call_api(self, return_data):
        return mocks.service_api_get_priorities_call(return_data)


class TestCompanyStatusSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.CompanyStatusSynchronizer
    model_class = CompanyStatus
    fixture = fixtures.API_COMPANY_STATUS_LIST

    def call_api(self, return_data):
        return mocks.company_api_get_company_statuses_call(return_data)

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


class TestLocationSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.LocationSynchronizer
    model_class = Location
    fixture = fixtures.API_SERVICE_LOCATION_LIST

    def _assert_fields(self, location, api_location):
        self.assertEqual(location.name, api_location['name'])
        self.assertEqual(location.id, api_location['id'])
        self.assertEqual(location.where, api_location['where'])

    def setUp(self):
        self.synchronizer = sync.LocationSynchronizer()

    def call_api(self, return_data):
        return mocks.service_api_get_locations_call(return_data)


class TestBoardSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.BoardSynchronizer
    model_class = ConnectWiseBoard
    fixture = fixtures.API_BOARD_LIST

    def call_api(self, return_data):
        return mocks.service_api_get_boards_call(return_data)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.name, json_data['name'])
        self.assertEqual(instance.inactive, json_data['inactive'])


class TestBoardStatusSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.BoardStatusSynchronizer
    model_class = BoardStatus
    fixture = fixtures.API_BOARD_STATUS_LIST

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.name, json_data['name'])
        self.assertEqual(instance.sort_order, json_data['sortOrder'])
        self.assertEqual(instance.display_on_board,
                         json_data['displayOnBoard'])
        self.assertEqual(instance.inactive, json_data['inactive'])
        self.assertEqual(instance.closed_status, json_data['closedStatus'])

    def setUp(self):
        fixture_utils.init_boards()

    def call_api(self, return_data):
        return mocks.service_api_get_statuses_call(return_data)


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
        assert_sync_job(Member)


class TestOpportunityStatusSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.OpportunityStatusSynchronizer
    model_class = OpportunityStatus
    fixture = fixtures.API_SALES_OPPORTUNITY_STATUSES

    def call_api(self, return_data):
        return mocks.sales_api_get_opportunity_statuses_call(return_data)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.name, json_data['name'])
        self.assertEqual(instance.won_flag, json_data['wonFlag'])
        self.assertEqual(instance.lost_flag, json_data['lostFlag'])
        self.assertEqual(instance.closed_flag, json_data['closedFlag'])
        self.assertEqual(instance.inactive_flag, json_data['inactiveFlag'])


class TestOpportunitySynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.OpportunitySynchronizer
    model_class = Opportunity
    fixture = fixtures.API_SALES_OPPORTUNITIES

    def setUp(self):
        super().setUp()
        fixture_utils.init_opportunity_statuses()
        fixture_utils.init_opportunity_types()

    def call_api(self, return_data):
        return mocks.sales_api_get_opportunities_call(return_data)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.name, json_data['name'])
        self.assertEqual(instance.expected_close_date,
                         parse(json_data['expectedCloseDate']).date())
        self.assertEqual(instance.pipeline_change_date,
                         parse(json_data['pipelineChangeDate']))
        self.assertEqual(instance.date_became_lead,
                         parse(json_data['dateBecameLead']))
        self.assertEqual(instance.closed_date,
                         parse(json_data['closedDate']))
        self.assertEqual(instance.notes, json_data['notes'])
        self.assertEqual(instance.source, json_data['source'])
        self.assertEqual(instance.location_id, json_data['locationId'])

        self.assertEqual(instance.business_unit_id,
                         json_data['businessUnitId'])

        self.assertEqual(instance.customer_po,
                         json_data['customerPO'])

        self.assertEqual(instance.priority_id,
                         json_data['priority']['id'])

        self.assertEqual(instance.stage_id,
                         json_data['stage']['id'])

        self.assertEqual(instance.type_id,
                         json_data['type']['id'])

        self.assertEqual(instance.status_id,
                         json_data['status']['id'])

        self.assertEqual(instance.primary_sales_rep_id,
                         json_data['primarySalesRep']['id'])

        self.assertEqual(instance.secondary_sales_rep_id,
                         json_data['secondarySalesRep']['id'])

        self.assertEqual(instance.company_id,
                         json_data['company']['id'])

        self.assertEqual(instance.closed_by_id,
                         json_data['closedBy']['id'])


class TestOpportunityTypeSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.OpportunityTypeSynchronizer
    model_class = OpportunityType
    fixture = fixtures.API_SALES_OPPORTUNITY_TYPES

    def call_api(self, return_data):
        return mocks.sales_api_get_opportunity_types_call(return_data)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.description, json_data['description'])
        self.assertEqual(instance.inactive_flag, json_data['inactiveFlag'])

    def test_sync_update(self):
        self._sync(self.fixture)

        json_data = self.fixture[0]

        instance_id = json_data['id']
        original = self.model_class.objects \
            .get(id=instance_id)

        description = 'Some New Description'
        new_json = deepcopy(self.fixture[0])
        new_json['description'] = description
        new_json_list = [new_json]

        self._sync(new_json_list)

        changed = self.model_class.objects.get(id=instance_id)
        self.assertNotEqual(original.description,
                            description)
        self._assert_fields(changed, new_json)


class TestTicketSynchronizer(TestCase):

    def setUp(self):
        super().setUp()
        mocks.system_api_get_members_call(fixtures.API_MEMBER_LIST)
        mocks.system_api_get_member_image_by_identifier_call(
            (mocks.CW_MEMBER_IMAGE_FILENAME, mocks.get_member_avatar()))
        mocks.service_api_tickets_call()

        self._init_data()

    def _clean(self):
        Ticket.objects.all().delete()

    def _init_data(self):
        self._clean()

        fixture_utils.init_boards()
        fixture_utils.init_board_statuses()
        fixture_utils.init_teams()
        fixture_utils.init_members()
        fixture_utils.init_companies()
        fixture_utils.init_priorities()
        fixture_utils.init_projects()
        fixture_utils.init_locations()

    def _assert_sync(self, instance, json_data):
        self.assertEqual(instance.summary, json_data['summary'])
        self.assertEqual(instance.closed_flag, json_data.get('closedFlag'))
        self.assertEqual(instance.type, json_data.get('type'))
        self.assertEqual(instance.entered_date_utc,
                         parse(json_data.get('dateEntered')))
        self.assertEqual(instance.last_updated_utc,
                         parse(json_data.get('_info').get('lastUpdated')))
        self.assertEqual(instance.required_date_utc,
                         parse(json_data.get('requiredDate')))
        self.assertEqual(instance.resources, json_data.get('resources'))
        self.assertEqual(instance.budget_hours, json_data.get('budgetHours'))
        self.assertEqual(instance.actual_hours, json_data.get('actualHours'))
        self.assertEqual(instance.record_type, json_data.get('recordType'))
        self.assertEqual(instance.parent_ticket_id,
                         json_data.get('parentTicketId'))
        self.assertEqual(instance.has_child_ticket,
                         json_data.get('hasChildTicket'))

        self.assertEqual(instance.has_child_ticket,
                         json_data.get('hasChildTicket'))
        resource_names = set(json_data.get('resources').split(','))

        # verify members
        member_qset = instance.members.all()
        member_names = set(member_qset.values_list('identifier', flat=True))
        self.assertEqual(resource_names, member_names)

        # verify assigned team
        self.assertEqual(instance.team_id, json_data['team']['id'])

        # verify assigned board
        self.assertEqual(instance.board_id, json_data['board']['id'])

        # verify assigned company
        self.assertEqual(instance.company_id, json_data['company']['id'])

        # verify assigned priority
        self.assertEqual(instance.priority_id, json_data['priority']['id'])

        # verify assigned location
        self.assertEqual(instance.location_id,
                         json_data['serviceLocation']['id'])

        # verify assigned project
        self.assertEqual(instance.project_id,
                         json_data['project']['id'])

        # verify assigned status
        self.assertEqual(instance.status_id,
                         json_data['status']['id'])

    def test_sync_ticket(self):
        """Test to ensure ticket synchronizer saves an
        CW Ticket instance locally"""
        synchronizer = sync.TicketSynchronizer()
        synchronizer.sync()
        self.assertGreater(Ticket.objects.all().count(), 0)

        json_data = fixtures.API_SERVICE_TICKET
        instance = Ticket.objects.get(id=json_data['id'])
        self._assert_sync(instance, json_data)
        assert_sync_job(Ticket)

    def test_sync_updated(self):
        self._init_data()
        fixture_utils.init_tickets()
        updated_ticket_fixture = deepcopy(fixtures.API_SERVICE_TICKET)
        updated_ticket_fixture['summary'] = 'A new kind of summary'
        fixture_list = [updated_ticket_fixture]

        method_name = 'djconnectwise.api.ServiceAPIClient.get_tickets'
        mock_call, _patch = mocks.create_mock_call(method_name, fixture_list)
        synchronizer = sync.TicketSynchronizer()
        synchronizer.sync()
        created_count, updated_count, _ = synchronizer.sync()

        self.assertEqual(created_count, 0)
        self.assertEqual(updated_count, len(fixture_list))

        instance = Ticket.objects.get(id=updated_ticket_fixture['id'])
        self._assert_sync(instance, updated_ticket_fixture)

    def test_delete_stale_tickets(self):
        """Local ticket should be deleted if omitted from sync"""
        fixture_utils.init_tickets()

        ticket_id = fixtures.API_SERVICE_TICKET['id']
        ticket_qset = Ticket.objects.filter(id=ticket_id)
        self.assertEqual(ticket_qset.count(), 1)

        method_name = 'djconnectwise.api.ServiceAPIClient.get_tickets'
        mock_call, _patch = mocks.create_mock_call(method_name, [])
        synchronizer = sync.TicketSynchronizer()
        synchronizer.sync(reset=True)
        self.assertEqual(ticket_qset.count(), 0)
        _patch.stop()


class TestSyncSettings(TestCase):

    def test_default_batch_size(self):
        synchronizer = sync.BoardSynchronizer()

        self.assertEqual(synchronizer.batch_size,
                         settings.DJCONNECTWISE_API_BATCH_LIMIT)

    def test_dynamic_batch_size(self):
        method_name = 'djconnectwise.utils.RequestSettings.get_settings'
        request_settings = {
            'batch_size': 10,
            'timeout': 10,
        }
        _, _patch = mocks.create_mock_call(method_name, request_settings)

        synchronizer = sync.BoardSynchronizer()

        self.assertEqual(synchronizer.batch_size,
                         request_settings['batch_size'])
        _patch.stop()


class MockSynchronizer:
    error_message = 'One heck of an error'
    model_class = Ticket

    @log_sync_job
    def sync(self):
        return 1, 2, 3

    @log_sync_job
    def sync_with_error(self):
        raise ValueError(self.error_message)


class TestSyncJob(TestCase):

    def setUp(self):
        self.synchronizer = MockSynchronizer()

    def assert_sync_job(self, created, updated, deleted, message, success):
        sync_job = SyncJob.objects.all().last()
        self.assertEqual(created, sync_job.added)
        self.assertEqual(updated, sync_job.updated)
        self.assertEqual(deleted, sync_job.deleted)
        self.assertEqual(self.synchronizer.model_class.__name__,
                         sync_job.entity_name)
        self.assertEqual(message, sync_job.message)
        self.assertEqual(sync_job.success, success)

    def test_sync_successful(self):
        self.assert_sync_job(*self.synchronizer.sync(), '', True)

    def test_sync_failed(self):

        try:
            self.synchronizer.sync_with_error()
        except Exception:
            pass

        self.assert_sync_job(0, 0, 0, self.synchronizer.error_message, False)
