from copy import deepcopy
from unittest import TestCase
from django.test import TransactionTestCase
from django.core.files.storage import default_storage

import datetime

from dateutil.parser import parse
from djconnectwise import models
from djconnectwise.utils import get_hash
from djconnectwise.sync import InvalidObjectException

from . import fixtures
from . import fixture_utils
from . import mocks
from .. import sync
from ..sync import log_sync_job


class AssertSyncMixin:

    def assert_sync_job(self):
        qset = \
            models.SyncJob.objects.filter(
                entity_name=self.model_class.__bases__[0].__name__
            )
        assert qset.exists()


class SynchronizerTestMixin(AssertSyncMixin):
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

    def _sync_with_results(self, return_data):
        _, get_patch = self.call_api(return_data)
        self.synchronizer = self.synchronizer_class()
        self.synchronizer.sync()
        return self.synchronizer.sync()

    def test_sync(self):
        self._sync(self.fixture)
        instance_dict = {c['id']: c for c in self.fixture}

        for instance in self.model_class.objects.all():
            json_data = instance_dict[instance.id]
            self._assert_fields(instance, json_data)

        self.assert_sync_job()

    def test_sync_update(self):
        self._sync(self.fixture)

        json_data = self.fixture[0]

        instance_id = json_data['id']
        original = self.model_class.objects.get(id=instance_id)

        name = 'Some New Name'
        new_json = deepcopy(self.fixture[0])
        new_json['name'] = name
        new_json_list = [new_json]

        self._sync(new_json_list)

        changed = self.model_class.objects.get(id=instance_id)

        self.assertNotEqual(original.name, name)
        self._assert_fields(changed, new_json)

    def test_sync_skips(self):
        self._sync(self.fixture)

        name = 'Some New Name'
        new_json = deepcopy(self.fixture[0])
        new_json['name'] = name
        new_json_list = [new_json]

        # Sync it twice to be sure that the data will be updated, then ignored
        self._sync(new_json_list)
        _, updated_count, skipped_count, _ = \
            self._sync_with_results(new_json_list)

        self.assertEqual(skipped_count, 1)
        self.assertEqual(updated_count, 0)


class TestBatchConditionMixin(TestCase):
    def test_get_optimal_size(self):
        synchronizer = sync.BatchConditionMixin()
        size = synchronizer.get_optimal_size(
            [31, 35, 43, 52, 58]
        )

        self.assertEqual(size, 5)

        size = synchronizer.get_optimal_size(
            [1, 2, 3, 43434, 54562, 54568, 65643],
            max_url_length=310,
            min_url_length=305,
        )
        self.assertEqual(size, 2)

        size = synchronizer.get_optimal_size(
            [442434, 53462, 552468, 63443],
            max_url_length=310,
            min_url_length=305,
        )
        self.assertEqual(size, 1)

        size = synchronizer.get_optimal_size(
            [1],
            max_url_length=310,
            min_url_length=305,
        )
        self.assertEqual(size, 1)

        size = synchronizer.get_optimal_size(
            [],
            max_url_length=310,
            min_url_length=305,
        )
        self.assertIsNone(size)


class TestTerritorySynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.TerritorySynchronizer
    model_class = models.TerritoryTracker
    fixture = fixtures.API_SYSTEM_TERRITORY_LIST

    def setUp(self):
        super().setUp()
        fixture_utils.init_territories()

    def call_api(self, return_data):
        return mocks.system_api_get_territories_call(return_data)

    def test_sync_update(self):
        self._sync(self.fixture)

        json_data = self.fixture[0]

        instance_id = json_data['id']
        original = self.model_class.objects.get(id=instance_id)

        name = 'A Different Territory'
        new_json = deepcopy(json_data)
        new_json['name'] = name
        new_json_list = [new_json]

        self._sync(new_json_list)

        changed = self.model_class.objects.get(id=instance_id)
        self.assertNotEqual(original.name, name)
        self._assert_fields(changed, new_json)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.name, json_data['name'])


class TestCompanySynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.CompanySynchronizer
    model_class = models.CompanyTracker
    fixture = fixtures.API_COMPANY_LIST

    def setUp(self):
        fixture_utils.init_territories()
        mocks.company_api_get_company_statuses_call(
            fixtures.API_COMPANY_STATUS_LIST)
        sync.CompanyStatusSynchronizer().sync()
        fixture_utils.init_company_types()

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
        self.assertEqual(
            company.company_types.first().id, api_company['types'][0]['id'])


class TestCompanyStatusSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.CompanyStatusSynchronizer
    model_class = models.CompanyStatusTracker
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


class TestCompanyTeamSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.CompanyTeamSynchronizer
    model_class = models.CompanyTeamTracker
    fixture = fixtures.API_COMPANY_TEAM_LIST

    def setUp(self):
        fixture_utils.init_company_team()

    def call_api(self, return_data):
        return mocks.company_api_get_company_team_call(return_data)

    def test_sync_update(self):
        self._sync(self.fixture)

        json_data = self.fixture[0]

        instance_id = json_data['id']
        original = self.model_class.objects.get(id=instance_id)

        new_json = deepcopy(self.fixture[0])
        new_json['techFlag'] = False
        new_json_list = [new_json]

        self._sync(new_json_list)

        changed = self.model_class.objects.get(id=instance_id)
        self.assertNotEqual(original.tech_flag, new_json['techFlag'])
        self._assert_fields(changed, new_json)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.account_manager_flag,
                         json_data['accountManagerFlag'])
        self.assertEqual(instance.tech_flag, json_data['techFlag'])
        self.assertEqual(instance.sales_flag, json_data['salesFlag'])


class TestCompanyTestRoleSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.CompanyTeamRoleSynchronizer
    model_class = models.CompanyTeamRoleTracker
    fixture = fixtures.API_COMPANY_TEAM_ROLE_LIST

    def setUp(self):
        fixture_utils.init_company_team_role()

    def call_api(self, return_data):
        return mocks.company_api_get_company_team_role_call(return_data)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.name, json_data['name'])
        self.assertEqual(instance.account_manager_flag,
                         json_data['accountManagerFlag'])
        self.assertEqual(instance.tech_flag, json_data['techFlag'])
        self.assertEqual(instance.sales_flag, json_data['salesFlag'])


class TestTimeEntrySynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.TimeEntrySynchronizer
    model_class = models.TimeEntryTracker
    fixture = fixtures.API_TIME_ENTRY_LIST

    def call_api(self, return_data):
        return mocks.time_api_get_time_entries_call(return_data)

    def test_sync_update(self):
        self._sync(self.fixture)

        json_data = self.fixture[0]

        instance_id = json_data['id']
        original = self.model_class.objects.get(id=instance_id)

        start = '2003-10-06T14:48:18Z'
        new_json = deepcopy(self.fixture[0])
        new_json["timeStart"] = start
        new_json_list = [new_json]

        self._sync(new_json_list)

        changed = self.model_class.objects.get(id=instance_id)
        self.assertNotEqual(original.time_start,
                            start)
        self._assert_fields(changed, new_json)

    def test_sync_skips(self):
        self._sync(self.fixture)

        start = '2003-10-06T14:48:18Z'
        new_json = deepcopy(self.fixture[0])
        new_json["timeStart"] = start
        new_json_list = [new_json]

        # Sync it twice to be sure that the data will be updated, then ignored
        self._sync(new_json_list)
        _, updated_count, skipped_count, _ = self._sync_with_results(
            new_json_list)

        self.assertEqual(skipped_count, 1)
        self.assertEqual(updated_count, 0)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.charge_to_id.id, json_data['chargeToId'])
        self.assertEqual(instance.charge_to_type, json_data['chargeToType'])
        self.assertEqual(instance.time_start, parse(json_data['timeStart']))
        self.assertEqual(instance.time_end, parse(json_data['timeEnd']))
        self.assertEqual(instance.actual_hours, json_data['actualHours'])
        self.assertEqual(instance.billable_option, json_data['billableOption'])
        self.assertEqual(instance.notes, json_data['notes'])


class TestCompanyTypeSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.CompanyTypeSynchronizer
    model_class = models.CompanyTypeTracker
    fixture = fixtures.API_COMPANY_TYPES_LIST

    def call_api(self, return_data):
        return mocks.company_api_get_company_types_call(return_data)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.name, json_data['name'])
        self.assertEqual(instance.vendor_flag, json_data['vendorFlag'])


class TestScheduleEntriesSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.ScheduleEntriesSynchronizer
    model_class = models.ScheduleEntryTracker
    fixture = fixtures.API_SCHEDULE_ENTRIES

    def setUp(self):
        super().setUp()
        fixture_utils.init_boards()
        fixture_utils.init_territories()
        fixture_utils.init_contacts()
        fixture_utils.init_project_statuses()
        fixture_utils.init_projects()
        fixture_utils.init_locations()
        fixture_utils.init_priorities()
        fixture_utils.init_members()
        fixture_utils.init_opportunity_stages()
        fixture_utils.init_opportunity_types()
        fixture_utils.init_opportunities()
        fixture_utils.init_board_statuses()
        fixture_utils.init_schedule_statuses()
        fixture_utils.init_schedule_types()
        fixture_utils.init_teams()
        fixture_utils.init_types()
        fixture_utils.init_subtypes()
        fixture_utils.init_items()
        fixture_utils.init_tickets()
        fixture_utils.init_activities()

    def call_api(self, return_data):
        return mocks.schedule_api_get_schedule_entries_call(return_data)

    def test_sync_update(self):
        self._sync(self.fixture)

        json_data = self.fixture[0]

        instance_id = json_data['id']
        original = self.model_class.objects.get(id=instance_id)

        name = 'Some New Name'
        new_json = deepcopy(self.fixture[0])
        new_json['name'] = name
        new_json_list = [new_json]

        self._sync(new_json_list)

        changed = self.model_class.objects.get(id=instance_id)
        self.assertNotEqual(original.name,
                            name)
        self._assert_fields(changed, new_json)

    def test_schedule_object_assignment(self):
        self._sync(self.fixture)

        json_data = self.fixture[0]

        schedule_entry = self.model_class.objects.get(id=json_data['id'])

        self.assertEqual(schedule_entry.schedule_type.identifier, "S")

        json_data = self.fixture[1]

        schedule_entry = self.model_class.objects.get(id=json_data['id'])

        self.assertEqual(schedule_entry.schedule_type.identifier, "C")

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.name, json_data['name'])
        self.assertEqual(instance.done_flag, json_data['doneFlag'])
        self.assertEqual(instance.date_start,
                         parse(json_data['dateStart']))
        self.assertEqual(instance.date_end,
                         parse(json_data['dateEnd']))

        # verify referenced objects
        if instance.activity_object is not None:
            self.assertEqual(instance.activity_object.id,
                             json_data['objectId'])
        if instance.ticket_object is not None:
            self.assertEqual(instance.ticket_object.id, json_data['objectId'])
        self.assertEqual(instance.where.id, json_data['where']['id'])
        self.assertEqual(instance.member.id, json_data['member']['id'])
        self.assertEqual(instance.status.id, json_data['status']['id'])
        self.assertEqual(instance.schedule_type.id, json_data['type']['id'])


class TestScheduleTypeSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.ScheduleTypeSynchronizer
    model_class = models.ScheduleTypeTracker
    fixture = fixtures.API_SCHEDULE_TYPE_LIST

    def call_api(self, return_data):
        return mocks.schedule_api_get_schedule_types_call(return_data)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.name, json_data['name'])


class TestScheduleStatusSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.ScheduleStatusSynchronizer
    model_class = models.ScheduleStatusTracker
    fixture = fixtures.API_SCHEDULE_STATUS_LIST

    def call_api(self, return_data):
        return mocks.schedule_api_get_schedule_statuses_call(return_data)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.name, json_data['name'])


class TestProjectStatusSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.ProjectStatusSynchronizer
    model_class = models.ProjectStatusTracker
    fixture = fixtures.API_PROJECT_STATUSES

    def call_api(self, return_data):
        return mocks.projects_api_get_project_statuses_call(return_data)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.name, json_data['name'])
        self.assertEqual(instance.default_flag, json_data['defaultFlag'])
        self.assertEqual(instance.inactive_flag, json_data['inactiveFlag'])
        self.assertEqual(instance.closed_flag, json_data['closedFlag'])


class TestProjectTypeSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.ProjectTypeSynchronizer
    model_class = models.ProjectTypeTracker
    fixture = fixtures.API_PROJECT_TYPES

    def call_api(self, return_data):
        return mocks.projects_api_get_project_types_call(return_data)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.name, json_data['name'])
        self.assertEqual(instance.default_flag, json_data['defaultFlag'])
        self.assertEqual(instance.inactive_flag, json_data['inactiveFlag'])


class TestProjectRoleSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.ProjectRoleSynchronizer
    model_class = models.ProjectRoleTracker
    fixture = fixtures.API_PROJECT_ROLE

    def call_api(self, return_data):
        return mocks.project_api_get_project_roles_call(return_data)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.name, json_data['name'])
        self.assertEqual(
            instance.manager_role_flag, json_data['managerRoleFlag'])
        self.assertEqual(
            instance.default_contact_flag, json_data['defaultContactFlag'])


class TestConfigurationStatusSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.ConfigurationStatusSynchronizer
    model_class = models.ConfigurationStatusTracker
    fixture = fixtures.API_CONFIGURATION_STATUS

    def call_api(self, return_data):
        return mocks.configuration_api_get_configuration_statuses(return_data)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.description, json_data['description'])
        self.assertEqual(instance.closed_flag, json_data['closedFlag'])
        self.assertEqual(instance.default_flag, json_data['defaultFlag'])

    def test_sync_update(self):
        self._sync(self.fixture)

        json_data = self.fixture[0]

        instance_id = json_data['id']
        original = self.model_class.objects.get(id=instance_id)

        description = 'Some New Description'
        new_json = deepcopy(self.fixture[0])
        new_json['description'] = description
        new_json_list = [new_json]

        self._sync(new_json_list)

        changed = self.model_class.objects.get(id=instance_id)

        self.assertNotEqual(original.description, description)
        self._assert_fields(changed, new_json)


class TestConfigurationTypeSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.ConfigurationTypeSynchronizer
    model_class = models.ConfigurationTypeTracker
    fixture = fixtures.API_CONFIGURATION_TYPES

    def call_api(self, return_data):
        return mocks.configuration_api_get_configuration_types(return_data)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.name, json_data['name'])
        self.assertEqual(instance.inactive_flag, json_data['inactiveFlag'])
        self.assertEqual(instance.system_flag, json_data['systemFlag'])


class TestProjectPhaseSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.ProjectPhaseSynchronizer
    model_class = models.ProjectPhaseTracker
    fixture = fixtures.API_PROJECT_PHASE_LIST

    def setUp(self):
        super().setUp()
        fixture_utils.init_project_statuses()
        fixture_utils.init_project_types()
        fixture_utils.init_boards()
        fixture_utils.init_projects()

    def call_api(self, return_data):
        return mocks.projects_api_get_project_phases_call(return_data)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.description, json_data['description'])
        self.assertEqual(instance.bill_time, json_data['billTime'])
        self.assertEqual(instance.notes, json_data['notes'])
        self.assertEqual(instance.scheduled_hours, json_data['scheduledHours'])
        self.assertEqual(instance.actual_hours, json_data['actualHours'])
        self.assertEqual(instance.budget_hours, json_data['budgetHours'])
        self.assertEqual(instance.project_id, json_data['projectId'])

        self.assertEqual(
            instance.scheduled_start, parse(json_data['scheduledStart']).date()
        )
        self.assertEqual(
            instance.scheduled_end, parse(json_data['scheduledEnd']).date()
        )
        self.assertEqual(
            instance.actual_start, parse(json_data['actualStart']).date()
        )
        self.assertEqual(
            instance.actual_end, parse(json_data['actualEnd']).date()
        )

    def test_sync_update(self):
        self._sync(self.fixture)

        json_data = self.fixture[0]

        instance_id = json_data['id']
        original = self.model_class.objects.get(id=instance_id)

        description = 'Some New Description'
        new_json = deepcopy(self.fixture[0])
        new_json['description'] = description
        new_json_list = [new_json]

        self._sync(new_json_list)

        changed = self.model_class.objects.get(id=instance_id)

        self.assertNotEqual(original.description, description)
        self._assert_fields(changed, new_json)

    def test_sync_skips(self):
        self._sync(self.fixture)

        description = 'Some New Description'
        new_json = deepcopy(self.fixture[0])
        new_json['description'] = description
        new_json_list = [new_json]

        # Sync it twice to be sure that the data will be updated, then ignored
        self._sync(new_json_list)
        _, updated_count, skipped_count, _ = \
            self._sync_with_results(new_json_list)

        self.assertEqual(skipped_count, 1)
        self.assertEqual(updated_count, 0)


class TestProjectSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.ProjectSynchronizer
    model_class = models.ProjectTracker
    fixture = fixtures.API_PROJECT_LIST

    def setUp(self):
        super().setUp()
        fixture_utils.init_project_statuses()
        fixture_utils.init_project_types()
        fixture_utils.init_boards()

    def call_api(self, return_data):
        return mocks.project_api_get_projects_call(return_data)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.name, json_data['name'])
        self.assertEqual(instance.manager_id, json_data['manager']['id'])
        self.assertAlmostEqual(
            float(instance.actual_hours),
            json_data['actualHours']
        )
        self.assertAlmostEqual(
            float(instance.budget_hours),
            json_data['budgetHours']
        )
        self.assertAlmostEqual(
            float(instance.scheduled_hours),
            json_data['scheduledHours']
        )
        self.assertEqual(
            instance.actual_start, parse(json_data['actualStart']).date()
        )
        self.assertEqual(
            instance.actual_end, parse(json_data['actualEnd']).date()
        )
        self.assertEqual(
            instance.estimated_start, parse(json_data['estimatedStart']).date()
        )
        self.assertEqual(
            instance.estimated_end, parse(json_data['estimatedEnd']).date()
        )


class TestTeamSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.TeamSynchronizer
    model_class = models.TeamTracker
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
    model_class = models.TicketPriorityTracker
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
            list(models.TicketPriority.DEFAULT_COLORS.values()) + \
            [models.TicketPriority.DEFAULT_COLOR]

    def call_api(self, return_data):
        return mocks.service_api_get_priorities_call(return_data)


class TestLocationSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.LocationSynchronizer
    model_class = models.LocationTracker
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
    model_class = models.ConnectWiseBoardTracker
    fixture = fixtures.API_BOARD_LIST

    def call_api(self, return_data):
        return mocks.service_api_get_boards_call(return_data)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.name, json_data['name'])
        self.assertEqual(instance.inactive, json_data['inactiveFlag'])
        self.assertEqual(instance.work_role.name,
                         json_data['workRole']['name'])
        self.assertEqual(instance.work_type.name,
                         json_data['workType']['name'])

    def setUp(self):
        super().setUp()
        fixture_utils.init_work_roles()
        fixture_utils.init_work_types()
        fixture_utils.init_boards()


class TestBoardStatusSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.BoardStatusSynchronizer
    model_class = models.BoardStatusTracker
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


class TestServiceNoteSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.ServiceNoteSynchronizer
    model_class = models.ServiceNoteTracker
    fixture = fixtures.API_SERVICE_NOTE_LIST

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.ticket.id, json_data['ticketId'])
        self.assertEqual(instance.text, json_data['text'])
        self.assertEqual(instance.detail_description_flag,
                         json_data['detailDescriptionFlag'])
        self.assertEqual(instance.internal_analysis_flag,
                         json_data['internalAnalysisFlag'])
        self.assertEqual(instance.resolution_flag, json_data['resolutionFlag'])
        self.assertEqual(instance.member.identifier,
                         json_data['member']['identifier'])
        self.assertEqual(instance.date_created,
                         parse(json_data['dateCreated']))
        self.assertEqual(instance.created_by, json_data['createdBy'])
        self.assertEqual(instance.internal_flag, json_data['internalFlag'])
        self.assertEqual(instance.external_flag, json_data['externalFlag'])

    def call_api(self, return_data):
        return mocks.service_api_get_notes_call(return_data)

    def test_sync_update(self):
        self._sync(self.fixture)

        json_data = self.fixture[0]

        instance_id = json_data['id']
        original = self.model_class.objects.get(id=instance_id)

        flag = False
        new_json = deepcopy(self.fixture[0])
        new_json['detailDescriptionFlag'] = flag
        new_json_list = [new_json]

        self._sync(new_json_list)

        changed = self.model_class.objects.get(id=instance_id)
        self.assertNotEqual(original.detail_description_flag,
                            flag)
        self._assert_fields(changed, new_json)

    def test_sync_skips(self):
        self._sync(self.fixture)

        new_json = deepcopy(self.fixture[0])
        new_json['detailDescriptionFlag'] = False
        new_json_list = [new_json]

        # Sync it twice to be sure that the data will be updated, then ignored
        self._sync(new_json_list)
        _, updated_count, skipped_count, _ = \
            self._sync_with_results(new_json_list)

        self.assertEqual(skipped_count, 1)
        self.assertEqual(updated_count, 0)


class TestOpportunityNoteSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.OpportunityNoteSynchronizer
    model_class = models.OpportunityNoteTracker
    fixture = fixtures.API_SALES_OPPORTUNITY_NOTE_LIST

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.text, json_data['text'])
        self.assertEqual(instance.opportunity.id,
                         json_data['opportunityId'])

    def setUp(self):
        super().setUp()
        fixture_utils.init_opportunity_notes()
        fixture_utils.init_opportunity_stages()
        fixture_utils.init_opportunities()

    def call_api(self, return_data):
        return mocks.sales_api_get_opportunity_notes_call(return_data)

    def test_sync_update(self):
        self._sync(self.fixture)

        json_data = self.fixture[0]

        instance_id = json_data['id']
        original = self.model_class.objects.get(id=instance_id)

        text = "Different Text, not the same text, but new, better text."
        new_json = deepcopy(self.fixture[0])
        new_json['text'] = text
        new_json_list = [new_json]

        self._sync(new_json_list)

        changed = self.model_class.objects.get(id=instance_id)
        self.assertNotEqual(original.text, text)
        self._assert_fields(changed, new_json)

    def test_sync_skips(self):
        self._sync(self.fixture)

        text = "Different Text, not the same text, but new, better text."
        new_json = deepcopy(self.fixture[0])
        new_json['text'] = text
        new_json_list = [new_json]

        # Sync it twice to be sure that the data will be updated, then ignored
        self._sync(new_json_list)
        _, updated_count, skipped_count, _ = \
            self._sync_with_results(new_json_list)

        self.assertEqual(skipped_count, 1)
        self.assertEqual(updated_count, 0)


class TestMemberSynchronization(TransactionTestCase, AssertSyncMixin):
    model_class = models.MemberTracker

    def setUp(self):
        fixture_utils.init_work_roles()
        self.identifier = 'User1'
        mocks.system_api_get_members_call([fixtures.API_MEMBER])
        self.synchronizer = sync.MemberSynchronizer()
        mocks.system_api_get_member_image_by_photo_id_call(
            (mocks.CW_MEMBER_IMAGE_FILENAME, mocks.get_member_avatar()))

    def _assert_member_fields(self, local_member, api_member):
        self.assertEqual(local_member.first_name, api_member['firstName'])
        self.assertEqual(local_member.last_name, api_member['lastName'])
        self.assertEqual(local_member.office_email, api_member['officeEmail'])

    def test_sync_member_update(self):
        member = models.Member()
        member.id = 176
        member.identifier = self.identifier
        member.first_name = 'some stale first name'
        member.last_name = 'some stale last name'
        member.office_email = 'some@stale.com'
        member.save()
        self.synchronizer.sync()
        local_member = models.Member.objects.get(identifier=self.identifier)
        api_member = fixtures.API_MEMBER
        self._assert_member_fields(local_member, api_member)

    def test_sync_member_create(self):
        self.synchronizer.sync()
        local_member = models.Member.objects.all().first()
        api_member = fixtures.API_MEMBER
        self._assert_member_fields(local_member, api_member)
        self.assert_sync_job()

    def test_sync_member_with_no_photo(self):
        member_without_photo = deepcopy(fixtures.API_MEMBER)
        member_without_photo.pop('photo')
        mocks.system_api_get_members_call([member_without_photo])
        self.synchronizer = sync.MemberSynchronizer()
        self.synchronizer.sync()
        local_member = models.Member.objects.get(identifier=self.identifier)
        self._assert_member_fields(local_member, member_without_photo)
        local_avatar = local_member.avatar
        self.assertFalse(local_avatar)

    def test_sync_member_avatar_name_is_updated(self):
        self.synchronizer = sync.MemberSynchronizer()
        self.synchronizer.sync()

        member = models.Member.objects.get(identifier=self.identifier)
        old_avatar = member.avatar
        member.avatar = 'new_image_name.png'
        self.synchronizer.sync()

        self.assertNotEqual(old_avatar, member.avatar)

    def test_avatar_thumbnails_are_in_storage(self):
        self.synchronizer = sync.MemberSynchronizer()
        self.synchronizer.sync()
        member = models.Member.objects.get(identifier=self.identifier)

        attachment_filename = 'some_new_image.png'
        avatar = mocks.get_member_avatar()
        self.synchronizer._save_avatar(member, avatar, attachment_filename)
        filename = '{}.{}'.format(get_hash(avatar), 'png')
        micro_avatar_size = filename + '20x20.png'
        avatar_size = filename + '80x80.png'

        self.assertTrue(default_storage.exists(avatar_size))
        self.assertTrue(default_storage.exists(micro_avatar_size))


class TestOpportunitySynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.OpportunitySynchronizer
    model_class = models.OpportunityTracker
    fixture = fixtures.API_SALES_OPPORTUNITIES

    def setUp(self):
        super().setUp()
        self.synchronizer = self.synchronizer_class()
        mocks.sales_api_get_opportunity_types_call(
            fixtures.API_SALES_OPPORTUNITY_TYPES)
        fixture_utils.init_activities()
        fixture_utils.init_opportunity_statuses()
        fixture_utils.init_opportunity_types()
        fixture_utils.init_sales_probabilities()
        fixture_utils.init_members()
        fixture_utils.init_territories()
        fixture_utils.init_companies()

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

        self.assertEqual(instance.opportunity_type_id,
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

    def test_fetch_sync_by_id(self):
        json_data = self.fixture[0]
        _, patch = mocks.sales_api_by_id_call(json_data)
        result = self.synchronizer.fetch_sync_by_id(json_data['id'])
        self._assert_fields(result, json_data)
        patch.stop()

    # TODO This test does nothing, must be updated
    # def test_fetch_delete_by_id(self):
    #     json_data = self.fixture[0]
    #     _, patch = mocks.sales_api_by_id_call(json_data)
    #     self.synchronizer.fetch_delete_by_id(json_data['id'])
    #     self.assertFalse(Opportunity.objects.filter(
    #         id=json_data['id']).exists())
    #     patch.stop()


class TestOpportunityStageSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.OpportunityStageSynchronizer
    model_class = models.OpportunityStageTracker
    fixture = fixtures.API_SALES_OPPORTUNITY_STAGES

    def call_api(self, return_data):
        return mocks.sales_api_get_opportunity_stages_call(return_data)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.name, json_data['name'])


class TestOpportunityStatusSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.OpportunityStatusSynchronizer
    model_class = models.OpportunityStatusTracker
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


class TestOpportunityTypeSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.OpportunityTypeSynchronizer
    model_class = models.OpportunityTypeTracker
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
        original = self.model_class.objects.get(id=instance_id)

        description = 'Some New Description'
        new_json = deepcopy(self.fixture[0])
        new_json['description'] = description
        new_json_list = [new_json]

        self._sync(new_json_list)

        changed = self.model_class.objects.get(id=instance_id)
        self.assertNotEqual(original.description,
                            description)
        self._assert_fields(changed, new_json)

    def test_sync_skips(self):
        self._sync(self.fixture)

        description = 'Some New Description'
        new_json = deepcopy(self.fixture[0])
        new_json['description'] = description
        new_json_list = [new_json]

        # Sync it twice to be sure that the data will be updated, then ignored
        self._sync(new_json_list)
        _, updated_count, skipped_count, _ = \
            self._sync_with_results(new_json_list)

        self.assertEqual(skipped_count, 1)
        self.assertEqual(updated_count, 0)


class TestHolidaySynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.HolidaySynchronizer
    model_class = models.HolidayTracker
    fixture = fixtures.API_SCHEDULE_HOLIDAY_MODEL_LIST

    def setUp(self):
        fixture_utils.init_holiday_lists()

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.name, json_data['name'])
        self.assertEqual(instance.all_day_flag, json_data['allDayFlag'])
        self.assertEqual(instance.date, parse(json_data['date']).date())
        self.assertEqual(
            instance.start_time, parse(json_data['timeStart']).time())
        self.assertEqual(instance.end_time, parse(json_data['timeEnd']).time())
        self.assertEqual(
            instance.holiday_list.id, json_data['holidayList']['id'])

    def call_api(self, return_data):
        return mocks.schedule_api_get_holidays_call(return_data)

    def test_sync_update(self):
        self._sync(self.fixture)
        json_data = self.fixture[0]
        instance_id = json_data['id']
        original = self.model_class.objects.get(id=instance_id)
        new_json = deepcopy(self.fixture[0])
        name = 'A new name'
        new_json['name'] = name
        new_json_list = [new_json]
        self._sync(new_json_list)
        changed = self.model_class.objects.get(id=instance_id)
        self.assertNotEqual(
            original.name,
            name)
        self._assert_fields(changed, new_json)


class TestHolidayListSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.HolidayListSynchronizer
    model_class = models.HolidayListTracker
    fixture = fixtures.API_SCHEDULE_HOLIDAY_LIST_LIST

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.name, json_data['name'])

    def call_api(self, return_data):
        return mocks.schedule_api_get_holiday_lists_call(return_data)

    def test_sync_update(self):
        self._sync(self.fixture)
        json_data = self.fixture[0]
        instance_id = json_data['id']
        original = self.model_class.objects.get(id=instance_id)
        new_json = deepcopy(self.fixture[0])
        name = 'A new name'
        new_json['name'] = name
        new_json_list = [new_json]
        self._sync(new_json_list)
        changed = self.model_class.objects.get(id=instance_id)
        self.assertNotEqual(original.name,
                            name)
        self._assert_fields(changed, new_json)


class TestCalendarSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.CalendarSynchronizer
    model_class = models.CalendarTracker
    fixture = fixtures.API_SCHEDULE_CALENDAR_LIST

    def setUp(self):
        fixture_utils.init_holiday_lists()

    def call_api(self, return_data):
        return mocks.schedule_api_get_calendars_call(return_data)

    def test_sync_update(self):
        self._sync(self.fixture)

        json_data = self.fixture[0]

        instance_id = json_data['id']
        original = self.model_class.objects.get(id=instance_id)

        name = 'A New Calendar'
        new_json = deepcopy(json_data)
        new_json['name'] = name
        new_json_list = [new_json]

        self._sync(new_json_list)

        changed = self.model_class.objects.get(id=instance_id)
        self.assertNotEqual(original.name, name)
        self._assert_fields(changed, new_json)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.name, json_data['name'])
        self.assertEqual(
            instance.monday_start_time,
            parse(json_data['mondayStartTime']).time()
            )
        self.assertEqual(
            instance.monday_end_time,
            parse(json_data['mondayEndTime']).time()
            )
        self.assertEqual(
            instance.tuesday_start_time,
            parse(json_data['tuesdayStartTime']).time()
            )
        self.assertEqual(
            instance.tuesday_end_time,
            parse(json_data['tuesdayEndTime']).time()
            )
        self.assertEqual(
            instance.wednesday_start_time,
            parse(json_data['wednesdayStartTime']).time()
            )
        self.assertEqual(
            instance.wednesday_end_time,
            parse(json_data['wednesdayEndTime']).time()
            )
        self.assertEqual(
            instance.thursday_start_time,
            parse(json_data['thursdayStartTime']).time()
            )
        self.assertEqual(
            instance.thursday_end_time,
            parse(json_data['thursdayEndTime']).time()
            )
        self.assertEqual(
            instance.friday_start_time,
            parse(json_data['fridayStartTime']).time()
            )
        self.assertEqual(
            instance.friday_end_time,
            parse(json_data['fridayEndTime']).time()
            )
        # Dont parse these ones they are None in the fixtures
        self.assertEqual(
            instance.saturday_start_time,
            json_data['saturdayStartTime']
            )
        self.assertEqual(
            instance.saturday_end_time,
            json_data['saturdayEndTime']
            )
        self.assertEqual(
            instance.sunday_start_time,
            json_data['sundayStartTime']
            )
        self.assertEqual(
            instance.sunday_end_time,
            json_data['sundayEndTime']
            )


class TestMyCompanyOtherSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.MyCompanyOtherSynchronizer
    model_class = models.MyCompanyOtherTracker
    fixture = fixtures.API_SYSTEM_OTHER_LIST

    def setUp(self):
        fixture_utils.init_calendars()
        fixture_utils.init_others()

    def call_api(self, return_data):
        return mocks.system_api_get_other_call(return_data)

    def test_sync_update(self):
        self._sync(self.fixture)

        json_data = self.fixture[0]

        instance_id = json_data['id']
        original = self.model_class.objects.get(id=instance_id)

        new_json = deepcopy(json_data)
        new_json['defaultCalendar'] = None
        new_json_list = [new_json]

        self._sync(new_json_list)

        changed = self.model_class.objects.get(id=instance_id)
        self.assertNotEqual(
            original.default_calendar, changed.default_calendar)

    def test_sync_skips(self):
        self._sync(self.fixture)

        new_json = deepcopy(self.fixture[0])
        new_json['defaultCalendar'] = None
        new_json_list = [new_json]

        # Sync it twice to be sure that the data will be updated, then ignored
        self._sync(new_json_list)
        _, updated_count, skipped_count, _ = \
            self._sync_with_results(new_json_list)

        self.assertEqual(skipped_count, 1)
        self.assertEqual(updated_count, 0)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])


class TestTicketSynchronizerMixin(AssertSyncMixin):
    model_class = models.TicketTracker

    def setUp(self):
        super().setUp()
        mocks.system_api_get_members_call(fixtures.API_MEMBER_LIST)
        mocks.system_api_get_member_image_by_photo_id_call(
            (mocks.CW_MEMBER_IMAGE_FILENAME, mocks.get_member_avatar()))

    def _clean(self):
        models.Ticket.objects.all().delete()

    def _init_data(self):
        self._clean()

        fixture_utils.init_holiday_lists()
        fixture_utils.init_calendars()
        fixture_utils.init_board_statuses()
        fixture_utils.init_teams()
        fixture_utils.init_types()
        fixture_utils.init_subtypes()
        fixture_utils.init_items()

    def test_sync_ticket(self):
        """
        Test to ensure ticket synchronizer saves a CW Ticket instance
        locally.
        """
        synchronizer = self.sync_class()
        synchronizer.sync()
        self.assertGreater(models.Ticket.objects.all().count(), 0)

        json_data = self.ticket_fixture
        instance = models.Ticket.objects.get(id=json_data['id'])

        self._assert_sync(instance, json_data)
        self.assert_sync_job()

    def test_sync_ticket_truncates_automatic_cc_field(self):
        """
        Test to ensure ticket synchronizer truncates the automatic CC field
        to 1000 characters.
        """
        synchronizer = self.sync_class()

        instance = models.Ticket()

        field_data = "kanban@kanban.com;"
        for i in range(6):
            # Make some field data with length 1152
            field_data = field_data + field_data

        json_data = deepcopy(self.ticket_fixture)
        json_data['automaticEmailCc'] = field_data
        instance = synchronizer._assign_field_data(instance, json_data)
        self.assertEqual(len(instance.automatic_email_cc), 1000)

    def test_sync_child_tickets(self):
        """
        Test to ensure that a ticket will sync related objects,
        in its case schedule, note, and time entries
        """
        fixture_utils.init_schedule_entries()
        fixture_utils.init_service_notes()
        synchronizer = self.sync_class()

        ticket = models.Ticket.objects.get(id=self.ticket_fixture['id'])

        # Change some fields on all child objects
        updated_fixture = deepcopy(fixtures.API_SERVICE_NOTE_LIST[0])
        updated_fixture['ticketId'] = ticket.id
        updated_fixture['text'] = 'Some new text'
        fixture_list = [updated_fixture]

        method_name = 'djconnectwise.api.ServiceAPIClient.get_notes'
        mock_call, _patch = mocks.create_mock_call(method_name, fixture_list)

        _, _task_patch = mocks.create_mock_call(
            "djconnectwise.sync.TicketTaskSynchronizer.sync_tasks",
            None
        )

        updated_fixture = deepcopy(fixtures.API_TIME_ENTRY)
        updated_fixture['chargeToId'] = ticket.id
        updated_fixture['text'] = 'Some new text'
        updated_fixture['timeEnd'] = '2005-05-16T15:00:00Z'
        fixture_list = [updated_fixture]

        method_name = 'djconnectwise.api.TimeAPIClient.get_time_entries'
        mock_call, _patch = mocks.create_mock_call(method_name, fixture_list)

        updated_fixture = deepcopy(fixtures.API_SALES_ACTIVITY)
        fixture_list = [updated_fixture]

        method_name = 'djconnectwise.api.SalesAPIClient.get_activities'
        mock_call, _patch = mocks.create_mock_call(method_name, fixture_list)

        method_name = 'djconnectwise.api.TicketAPIMixin.get_ticket'
        mock_call, _patch = \
            mocks.create_mock_call(method_name, self.ticket_fixture)

        # Trigger method called on callback
        synchronizer.fetch_sync_by_id(ticket.id)

        # Get the new Values from the db
        updated_note = models.ServiceNote.objects.filter(ticket=ticket)[0]

        updated_time = models.TimeEntry.objects.filter(charge_to_id=ticket)[0]

        _task_patch.stop()

        # Confirm that they have all been updated
        self.assertEqual('Some new text', updated_note.text)
        self.assertEqual(
            datetime.datetime(
                2005, 5, 16, 15, 0, tzinfo=datetime.timezone.utc),
            updated_time.time_end
            )

    def test_sync_updated(self):

        updated_ticket_fixture = deepcopy(self.ticket_fixture)
        updated_ticket_fixture['summary'] = 'A new kind of summary'
        fixture_list = [updated_ticket_fixture]

        method_name = 'djconnectwise.api.TicketAPIMixin.get_tickets'
        mock_call, _patch = mocks.create_mock_call(method_name, fixture_list)
        synchronizer = self.sync_class()
        created_count, updated_count, _, _ = synchronizer.sync()

        self.assertEqual(created_count, 0)
        self.assertEqual(updated_count, len(fixture_list))

        instance = models.Ticket.objects.get(id=updated_ticket_fixture['id'])
        self._assert_sync(instance, updated_ticket_fixture)

    def test_sync_skips(self):

        # Update the ticket to know it skips it the second time
        updated_ticket_fixture = deepcopy(self.ticket_fixture)
        updated_ticket_fixture['summary'] = 'A new kind of summary'
        fixture_list = [updated_ticket_fixture]

        method_name = 'djconnectwise.api.TicketAPIMixin.get_tickets'
        _, _patch = mocks.create_mock_call(method_name, fixture_list)
        synchronizer = self.sync_class()
        # Synchronizer is called twice, as we are testing that  when
        # synchronizers are called twice it skips the record if no change is
        # detected.
        synchronizer.sync()
        created_count, _, skipped_count, _ = synchronizer.sync()

        self.assertEqual(created_count, 0)
        self.assertEqual(skipped_count, len(fixture_list))

        instance = models.Ticket.objects.get(id=updated_ticket_fixture['id'])
        self._assert_sync(instance, updated_ticket_fixture)

    def test_sync_multiple_status_batches(self):
        self._init_data()
        fixture_utils.init_tickets()
        updated_ticket_fixture = deepcopy(self.ticket_fixture)
        updated_ticket_fixture['summary'] = 'A new kind of summary'
        fixture_list = [updated_ticket_fixture]

        method_name = 'djconnectwise.api.TicketAPIMixin.get_tickets'
        mock_call, _patch = mocks.create_mock_call(method_name, fixture_list)
        synchronizer = sync.ServiceTicketSynchronizer()
        synchronizer.client.request_settings['max_url_length'] = 330
        synchronizer.batch_condition_list.extend(
            [234234, 345345, 234213, 2344523, 345645]
        )
        created_count, updated_count, _, _ = synchronizer.sync()

        self.assertEqual(mock_call.call_count, 2)

    def test_delete_stale_tickets(self):
        """Local ticket should be deleted if omitted from sync"""
        ticket_id = self.ticket_fixture['id']
        ticket_qset = models.Ticket.objects.filter(id=ticket_id)
        self.assertEqual(ticket_qset.count(), 1)

        method_name = 'djconnectwise.api.TicketAPIMixin.get_tickets'
        mock_call, _patch = mocks.create_mock_call(method_name, [])
        synchronizer = self.sync_class(full=True)
        synchronizer.sync()
        self.assertEqual(ticket_qset.count(), 0)
        _patch.stop()

    def test_callback_sync_time_entry(self):
        # Sync initial time entry
        mocks.time_api_get_time_entries_call(fixtures.API_TIME_ENTRY_LIST)
        time_entry_sync = sync.TimeEntrySynchronizer()
        time_entry_sync.sync()
        self.assertGreater(
            models.SyncJob.objects.filter(entity_name='TimeEntry').count(), 0
        )

        # Mock the child class syncs
        mocks.service_api_get_notes_call(fixtures.API_SERVICE_NOTE_LIST)
        mocks.sales_api_get_activities_call(fixtures.API_SALES_ACTIVITIES)
        _, _task_patch = mocks.create_mock_call(
            "djconnectwise.sync.TicketTaskSynchronizer.sync_tasks",
            None
        )

        method_name = 'djconnectwise.sync.TicketSynchronizerMixin.get_single'
        mock_call, _patch = \
            mocks.create_mock_call(method_name, self.ticket_fixture)

        # Create new time entry to sync
        new_time_entry = deepcopy(fixtures.API_TIME_ENTRY)
        new_time_entry['id'] = 3
        mocks.time_api_get_time_entries_call([new_time_entry,
                                              fixtures.API_TIME_ENTRY])

        ticket_id = self.ticket_fixture['id']
        synchronizer = self.sync_class()
        # Simulate ticket getting updated by a callback
        synchronizer.fetch_sync_by_id(ticket_id)

        # Verify that no time entries are removed,
        # and that only one entry is added
        last_sync_job = \
            models.SyncJob.objects.filter(entity_name='TimeEntry').last()

        _task_patch.stop()

        self.assertEqual(last_sync_job.deleted, 0)
        self.assertEqual(last_sync_job.updated, 0)
        self.assertEqual(last_sync_job.added, 1)
        self.assertEqual(last_sync_job.sync_type, 'partial')


class TestServiceTicketSynchronizer(TestTicketSynchronizerMixin, TestCase):
    sync_class = sync.ServiceTicketSynchronizer
    ticket_fixture = fixtures.API_SERVICE_TICKET

    def setUp(self):
        super().setUp()
        self._init_data()
        fixture_utils.init_tickets()

    def _assert_sync(self, instance, json_data):
        self.assertEqual(instance.summary, json_data['summary'])
        self.assertEqual(instance.closed_flag, json_data.get('closedFlag'))
        self.assertEqual(instance.entered_date_utc,
                         parse(json_data.get('_info').get('dateEntered')))
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

        # verify assigned status
        self.assertEqual(instance.status_id,
                         json_data['status']['id'])

        # verify assigned type
        self.assertEqual(instance.type_id, json_data['type']['id'])

        # verify assigned type
        self.assertEqual(instance.sub_type_id, json_data['subType']['id'])

        # verify assigned type
        self.assertEqual(instance.sub_type_item_id, json_data['item']['id'])

        self.assertEqual(instance.bill_time, json_data['billTime'])
        self.assertEqual(instance.automatic_email_cc_flag,
                         json_data['automaticEmailCcFlag'])
        self.assertEqual(instance.automatic_email_contact_flag,
                         json_data['automaticEmailContactFlag'])
        self.assertEqual(instance.automatic_email_resource_flag,
                         json_data['automaticEmailResourceFlag'])
        self.assertEqual(instance.automatic_email_cc,
                         json_data['automaticEmailCc'])
        self.assertEqual(instance.agreement, json_data['agreement'])

    def test_project_tickets_not_deleted_during_sync(self):
        """
        Verify that during a sync of service tickets, no project tickets are
        removed.
        """
        synchronizer = self.sync_class(full=True)
        synchronizer.sync()

        self.assertTrue(
            models.Ticket.objects.get(id=self.ticket_fixture['id']))

        project_ticket = models.Ticket.objects.create(
            summary='Project ticket',
            record_type='ProjectTicket'
        )
        project_ticket.save()

        method_name = 'djconnectwise.api.TicketAPIMixin.get_tickets'
        mock_call, _patch = mocks.create_mock_call(method_name, [])
        synchronizer = self.sync_class(full=True)
        synchronizer.sync()

        # Verify that the service ticket has been removed and project ticket
        # still exists.
        self.assertEqual(
            models.Ticket.objects.get(id=project_ticket.id), project_ticket)
        self.assertFalse(
            models.Ticket.objects.filter(
                id=self.ticket_fixture['id']).exists())

    def test_callback_sync_service_note(self):
        # Sync initial service note
        mocks.service_api_get_notes_call(fixtures.API_SERVICE_NOTE_LIST)
        service_note_sync = sync.ServiceNoteSynchronizer()
        service_note_sync.sync()
        self.assertGreater(
            models.SyncJob.objects.filter(entity_name='ServiceNote').count(), 0
        )

        # Mock the child class syncs
        mocks.time_api_get_time_entries_call(fixtures.API_TIME_ENTRY_LIST)
        mocks.sales_api_get_activities_call(fixtures.API_SALES_ACTIVITIES)

        _, _task_patch = mocks.create_mock_call(
            "djconnectwise.sync.TicketTaskSynchronizer.sync_tasks",
            None
        )

        method_name = 'djconnectwise.sync.TicketSynchronizerMixin.get_single'
        mock_call, _patch = \
            mocks.create_mock_call(method_name, self.ticket_fixture)

        # Create new service note to sync
        new_service_note = deepcopy(fixtures.API_SERVICE_NOTE_LIST[0])
        new_service_note['id'] = self.ticket_fixture['id']
        mocks.service_api_get_notes_call(
            [new_service_note, fixtures.API_SERVICE_NOTE_LIST[0]]
        )

        ticket_id = self.ticket_fixture['id']
        synchronizer = self.sync_class()
        # Simulate ticket getting updated by a callback
        synchronizer.fetch_sync_by_id(ticket_id)

        # Verify that no notes are removed, and that only one note is added
        last_sync_job = \
            models.SyncJob.objects.filter(entity_name='ServiceNote').last()

        _task_patch.stop()

        self.assertEqual(last_sync_job.deleted, 0)
        self.assertEqual(last_sync_job.updated, 0)
        self.assertEqual(last_sync_job.added, 1)
        self.assertEqual(last_sync_job.sync_type, 'partial')


class TestProjectTicketSynchronizer(TestTicketSynchronizerMixin, TestCase):
    sync_class = sync.ProjectTicketSynchronizer
    ticket_fixture = fixtures.API_PROJECT_TICKET

    def setUp(self):
        super().setUp()
        mocks.project_api_tickets_call()

        self._init_data()
        fixture_utils.init_schedule_statuses()
        fixture_utils.init_schedule_types()
        fixture_utils.init_project_tickets()

    def _assert_sync(self, instance, json_data):
        self.assertEqual(instance.summary, json_data['summary'])
        self.assertEqual(instance.closed_flag, json_data.get('closedFlag'))
        self.assertEqual(instance.last_updated_utc,
                         parse(json_data.get('_info').get('lastUpdated')))
        self.assertEqual(instance.required_date_utc,
                         parse(json_data.get('requiredDate')))
        self.assertEqual(instance.resources, json_data.get('resources'))
        self.assertEqual(instance.budget_hours, json_data.get('budgetHours'))
        self.assertEqual(instance.actual_hours, json_data.get('actualHours'))

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

        # verify assigned type
        self.assertEqual(instance.type_id, json_data['type']['id'])

        # verify assigned subtype
        self.assertEqual(instance.sub_type_id, json_data['subType']['id'])

        # verify assigned subtype item
        self.assertEqual(instance.sub_type_item_id, json_data['item']['id'])

        self.assertEqual(instance.bill_time, json_data['billTime'])
        self.assertEqual(instance.automatic_email_cc_flag,
                         json_data['automaticEmailCcFlag'])
        self.assertEqual(instance.automatic_email_contact_flag,
                         json_data['automaticEmailContactFlag'])
        self.assertEqual(instance.automatic_email_resource_flag,
                         json_data['automaticEmailResourceFlag'])
        self.assertEqual(instance.automatic_email_cc,
                         json_data['automaticEmailCc'])
        self.assertEqual(instance.agreement, json_data['agreement'])

    def test_service_tickets_not_deleted_during_sync(self):
        """
        Verify that during a sync of project tickets, no service tickets are
        removed.
        """
        synchronizer = self.sync_class(full=True)
        synchronizer.sync()
        self.assertTrue(
            models.Ticket.objects.get(id=self.ticket_fixture['id']))

        service_ticket = models.Ticket.objects.create(
            summary='Service ticket',
            record_type='ServiceTicket'
        )
        service_ticket.save()

        method_name = 'djconnectwise.api.TicketAPIMixin.get_tickets'
        mock_call, _patch = mocks.create_mock_call(method_name, [])
        synchronizer = self.sync_class(full=True)
        synchronizer.sync()

        # Verify that the project ticket has been removed and service ticket
        # still exists.
        self.assertEqual(
            models.Ticket.objects.get(id=service_ticket.id), service_ticket)
        self.assertFalse(
            models.Ticket.objects.filter(
                id=self.ticket_fixture['id']).exists())


class TestActivityStatusSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.ActivityStatusSynchronizer
    model_class = models.ActivityStatusTracker
    fixture = fixtures.API_SALES_ACTIVITY_STATUSES

    def call_api(self, return_data):
        return mocks.sales_api_get_activities_statuses_call(return_data)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.name, json_data['name'])
        self.assertEqual(instance.default_flag, json_data['defaultFlag'])
        self.assertEqual(instance.inactive_flag, json_data['inactiveFlag'])
        self.assertEqual(
            instance.spawn_followup_flag,
            json_data.get('spawnFollowupFlag', False)
        )
        self.assertEqual(instance.closed_flag, json_data['closedFlag'])


class TestActivityTypeSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.ActivityTypeSynchronizer
    model_class = models.ActivityTypeTracker
    fixture = fixtures.API_SALES_ACTIVITY_TYPES

    def call_api(self, return_data):
        return mocks.sales_api_get_activities_types_call(return_data)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.name, json_data['name'])
        self.assertEqual(instance.name, json_data['name'])
        self.assertEqual(instance.default_flag, json_data['defaultFlag'])
        self.assertEqual(instance.inactive_flag, json_data['inactiveFlag'])
        self.assertEqual(instance.email_flag, json_data['emailFlag'])
        self.assertEqual(instance.memo_flag, json_data['memoFlag'])
        self.assertEqual(instance.history_flag, json_data['historyFlag'])


class TestActivitySynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.ActivitySynchronizer
    model_class = models.ActivityTracker
    fixture = fixtures.API_SALES_ACTIVITIES

    def setUp(self):
        super().setUp()
        fixture_utils.init_work_roles()
        fixture_utils.init_work_types()
        mocks.system_api_get_member_image_by_photo_id_call(
            (mocks.CW_MEMBER_IMAGE_FILENAME, mocks.get_member_avatar()))
        fixture_utils.init_members()
        fixture_utils.init_territories()
        fixture_utils.init_company_statuses()
        fixture_utils.init_company_types()
        fixture_utils.init_companies()
        fixture_utils.init_contacts()
        fixture_utils.init_agreements()
        fixture_utils.init_sales_probabilities()
        fixture_utils.init_opportunity_types()
        fixture_utils.init_opportunity_stages()
        fixture_utils.init_opportunity_statuses()
        fixture_utils.init_opportunities()
        fixture_utils.init_agreements()
        fixture_utils.init_activity_statuses()
        fixture_utils.init_activity_types()
        fixture_utils.init_activities()

    def call_api(self, return_data):
        return mocks.sales_api_get_activities_call(return_data)

    def _get_datetime(self, instance, date_field):
        date_field = instance.get(date_field)
        if date_field:
            date_field = parse(date_field, default=parse('00:00Z'))

        return date_field

    def _assert_fields(self, activity, api_activity):
        self.assertEqual(activity.name, api_activity['name'])
        self.assertEqual(activity.notes, api_activity['notes'])
        self.assertEqual(activity.date_start,
                         self._get_datetime(api_activity, 'dateStart')
                         )
        self.assertEqual(activity.date_end,
                         self._get_datetime(api_activity, 'dateEnd')
                         )
        self.assertEqual(activity.assign_to_id, api_activity['assignTo']['id'])
        self.assertEqual(activity.opportunity_id,
                         api_activity['opportunity']['id'])
        if api_activity['ticket'] is not None:
            self.assertEqual(activity.ticket_id, api_activity['ticket']['id'])
        self.assertEqual(
            activity.status_id, api_activity['status']['id']
        )
        self.assertEqual(
            activity.type_id, api_activity['type']['id']
        )
        self.assertEqual(
            activity.company_id, api_activity['company']['id']
        )
        self.assertEqual(
            activity.agreement_id, api_activity['agreement']['id']
        )

    def test_sync_null_member_activity(self):
        null_member_activity = deepcopy(fixtures.API_SALES_ACTIVITY)
        null_member_activity['id'] = 999
        null_member_activity['assignTo'] = {'id': 99999}  # Member that does
        # not exist
        activity_list = [null_member_activity]

        method_name = 'djconnectwise.api.SalesAPIClient.get_activities'
        mock_call, _patch = \
            mocks.create_mock_call(method_name, activity_list)
        synchronizer = sync.ActivitySynchronizer(full=True)

        created_count, updated_count, skipped_count, deleted_count = \
            synchronizer.sync()

        # The existing Activity (#47) should be deleted since it is not
        # returned from when the sync is run.
        self.assertEqual(created_count, 0)
        self.assertEqual(updated_count, 0)
        self.assertEqual(deleted_count, 1)

    def test_sync_activity_null_assign_to(self):
        """
        Verify that an activity with a null 'assignTo' field is skipped.
        """
        null_assign_to_activity = deepcopy(fixtures.API_SALES_ACTIVITY)
        null_assign_to_activity['id'] = 888
        null_assign_to_activity['assignTo'] = None
        activity_list = [null_assign_to_activity]

        method_name = 'djconnectwise.api.SalesAPIClient.get_activities'
        mock_call, _patch = \
            mocks.create_mock_call(method_name, activity_list)
        synchronizer = sync.ActivitySynchronizer(full=True)

        created_count, updated_count, skipped_count, deleted_count = \
            synchronizer.sync()

        self.assertRaises(InvalidObjectException)
        self.assertEqual(created_count, 0)
        self.assertEqual(updated_count, 0)


class TestSyncTicketTasks(TestCase):

    def setUp(self):
        self.ticket = models.Ticket()
        self.ticket.save()

    def tearDown(self):
        self.ticket.delete()

    def test_sync_tasks(self):
        mocks.create_mock_call(
            "djconnectwise.sync.ServiceTicketTaskSynchronizer.get",
            [
                {'closed_flag': False},
                {'closed_flag': True},
                {'closed_flag': False}
            ]
        )

        self.assertIsNone(self.ticket.tasks_total)
        self.assertIsNone(self.ticket.tasks_completed)

        synchronizer = sync.ServiceTicketTaskSynchronizer()
        synchronizer.sync_items(self.ticket)

        self.assertEqual(3, self.ticket.tasks_total)
        self.assertEqual(1, self.ticket.tasks_completed)


class TestSyncSettings(TestCase):

    def test_default_batch_size(self):
        synchronizer = sync.BoardSynchronizer()
        self.assertEqual(synchronizer.batch_size, 50)

    def test_dynamic_batch_size(self):
        method_name = 'djconnectwise.utils.DjconnectwiseSettings.get_settings'
        request_settings = {
            'batch_size': 10,
            'timeout': 10.0,
        }
        _, _patch = mocks.create_mock_call(method_name, request_settings)

        synchronizer = sync.BoardSynchronizer()

        self.assertEqual(synchronizer.batch_size,
                         request_settings['batch_size'])
        _patch.stop()


class MockSynchronizer:
    error_message = 'One heck of an error'
    model_class = models.TicketTracker
    full = False

    @log_sync_job
    def sync(self):
        return 1, 2, 3, 4

    @log_sync_job
    def sync_with_error(self):
        raise ValueError(self.error_message)


class TestSyncJob(TestCase):

    def setUp(self):
        self.synchronizer = MockSynchronizer()

    def assert_sync_job(self, created, updated, skipped, deleted, message,
                        success):
        sync_job = models.SyncJob.objects.all().last()
        self.assertEqual(created, sync_job.added)
        self.assertEqual(updated, sync_job.updated)
        self.assertEqual(skipped, sync_job.skipped)
        self.assertEqual(deleted, sync_job.deleted)
        self.assertEqual(self.synchronizer.model_class.__bases__[0].__name__,
                         sync_job.entity_name)
        self.assertEqual(message, sync_job.message)
        self.assertEqual(sync_job.success, success)
        self.assertEqual(sync_job.sync_type, "partial")

    def test_sync_successful(self):
        created, updated, skipped, deleted = self.synchronizer.sync()
        self.assert_sync_job(created, updated, skipped, deleted, None, True)

    def test_sync_failed(self):
        try:
            self.synchronizer.sync_with_error()
        except Exception:
            pass

        self.assert_sync_job(
            0, 0, 0, 0, self.synchronizer.error_message, False)


class TestTypeSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.TypeSynchronizer
    model_class = models.TypeTracker
    fixture = fixtures.API_TYPE_LIST

    def setUp(self):
        super().setUp()
        fixture_utils.init_types()
        fixture_utils.init_boards()

    def call_api(self, return_data):
        return mocks.service_api_get_types_call(return_data)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.name, json_data['name'])
        self.assertEqual(instance.board.name, json_data['board']['name'])


class TestSubTypeSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.SubTypeSynchronizer
    model_class = models.SubTypeTracker
    fixture = fixtures.API_SUBTYPE_LIST

    def setUp(self):
        super().setUp()
        fixture_utils.init_subtypes()
        fixture_utils.init_boards()

    def call_api(self, return_data):
        return mocks.service_api_get_subtypes_call(return_data)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.name, json_data['name'])
        self.assertEqual(instance.board.name, json_data['board']['name'])


class TestItemSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.ItemSynchronizer
    model_class = models.ItemTracker
    fixture = fixtures.API_ITEM_LIST

    def setUp(self):
        super().setUp()
        fixture_utils.init_items()
        fixture_utils.init_boards()

    def call_api(self, return_data):
        return mocks.service_api_get_items_call(return_data)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.name, json_data['name'])
        self.assertEqual(instance.board.name, json_data['board']['name'])


class TestWorkTypeSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.WorkTypeSynchronizer
    model_class = models.WorkTypeTracker
    fixture = fixtures.API_WORK_TYPE_LIST

    def setUp(self):
        super().setUp()
        fixture_utils.init_work_types()

    def call_api(self, return_data):
        return mocks.time_api_get_work_types_call(return_data)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.name, json_data['name'])
        self.assertEqual(instance.inactive_flag, json_data['inactiveFlag'])


class TestWorkRoleSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.WorkRoleSynchronizer
    model_class = models.WorkRoleTracker
    fixture = fixtures.API_WORK_ROLE_LIST

    def setUp(self):
        super().setUp()
        fixture_utils.init_work_roles()

    def call_api(self, return_data):
        return mocks.time_api_get_work_roles_call(return_data)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.name, json_data['name'])
        self.assertEqual(instance.inactive_flag, json_data['inactiveFlag'])


class TestAgreementSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.AgreementSynchronizer
    model_class = models.AgreementTracker
    fixture = fixtures.API_AGREEMENT_LIST

    def setUp(self):
        super().setUp()
        fixture_utils.init_work_roles()
        fixture_utils.init_work_types()
        fixture_utils.init_territories()
        fixture_utils.init_company_statuses()
        fixture_utils.init_company_types()
        fixture_utils.init_companies()

    def call_api(self, return_data):
        return mocks.finance_api_get_agreements_call(return_data)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])
        self.assertEqual(instance.name, json_data['name'])
        self.assertEqual(instance.bill_time, json_data['billTime'])
        self.assertEqual(instance.agreement_type, json_data['type']['name'])
        self.assertEqual(instance.cancelled_flag, json_data['cancelledFlag'])
        self.assertEqual(
            instance.work_role.name, json_data['workRole']['name'])
        self.assertEqual(
            instance.work_type.name, json_data['workType']['name'])
        self.assertEqual(instance.company.name, json_data['company']['name'])


class TestProjectTeamMemberSynchronizer(TestCase, SynchronizerTestMixin):
    synchronizer_class = sync.ProjectTeamMemberSynchronizer
    model_class = models.ProjectTeamMemberTracker
    fixture = fixtures.API_PROJECT_TEAM_MEMBER_LIST

    def setUp(self):
        super().setUp()
        mocks.system_api_get_member_image_by_photo_id_call(
            (mocks.CW_MEMBER_IMAGE_FILENAME, mocks.get_member_avatar()))
        fixture_utils.init_members()
        fixture_utils.init_work_roles()
        fixture_utils.init_project_roles()
        fixture_utils.init_project_statuses()
        fixture_utils.init_boards()
        fixture_utils.init_projects()
        fixture_utils.init_project_team_members()

    def call_api(self, return_data):
        return mocks.project_api_get_team_members_call(return_data)

    def _assert_fields(self, instance, json_data):
        self.assertEqual(instance.id, json_data['id'])

    def test_sync_update(self):
        self._sync(self.fixture)

        json_data = self.fixture[0]

        instance_id = json_data['id']
        original = self.model_class.objects.get(id=instance_id)

        end_date = '2020-10-15T08:00:00Z'
        new_json = deepcopy(self.fixture[0])
        new_json['endDate'] = end_date
        new_json_list = [new_json]

        self._sync(new_json_list)

        changed = self.model_class.objects.get(id=instance_id)

        self.assertNotEqual(original.end_date, end_date)
        self._assert_fields(changed, new_json)

    def test_sync_skips(self):
        self._sync(self.fixture)

        end_date = '2020-10-15T08:00:00Z'
        new_json = deepcopy(self.fixture[0])
        new_json['endDate'] = end_date
        new_json_list = [new_json]

        # Sync it twice to be sure that the data will be updated, then ignored
        self._sync(new_json_list)
        _, updated_count, skipped_count, _ = self._sync_with_results(
            new_json_list)

        self.assertEqual(skipped_count, 1)
        self.assertEqual(updated_count, 0)
