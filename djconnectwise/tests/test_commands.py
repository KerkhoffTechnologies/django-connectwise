import io
import unittest

from django.core.management import call_command
from django.test import TestCase

from djconnectwise import models
from djconnectwise import callback

from django.db import transaction

from . import mocks
from . import fixtures
from . import fixture_utils
from .. import sync


def sync_summary(class_name, created_count):
    return '{} Sync Summary - Created: {}, Updated: 0'.format(
        class_name, created_count
    )


def full_sync_summary(class_name, deleted_count):
    return '{} Sync Summary - Created: 0, Updated: 0, Deleted: {}'.format(
        class_name, deleted_count
    )


def slug_to_title(slug):
    return slug.title().replace('_', ' ')


class AbstractBaseSyncTest(object):

    def _test_sync(self, mock_call, return_value, cw_object,
                   full_option=False):
        mock_call(return_value)
        out = io.StringIO()

        args = ['cwsync', cw_object]
        if full_option:
            args.append('--full')

        call_command(*args, stdout=out)
        return out

    def _title_for_cw_object(self, cw_object):
        return cw_object.title().replace('_', ' ')

    def test_sync(self):
        out = self._test_sync(*self.args)
        obj_title = self._title_for_cw_object(self.args[-1])
        self.assertIn(obj_title, out.getvalue().strip())

    def test_full_sync(self):
        self.test_sync()
        mock_call, return_value, cw_object = self.args
        args = [
            mock_call,
            [],
            cw_object
        ]

        out = self._test_sync(*args, full_option=True)
        obj_label = self._title_for_cw_object(cw_object)
        msg_tmpl = '{} Sync Summary - Created: 0, Updated: 0, Deleted: {}'
        msg = msg_tmpl.format(obj_label, len(return_value))
        self.assertEqual(msg, out.getvalue().strip())


class TestSyncCalendarsCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.schedule_api_get_calendar_call,
        fixutres.API_SCHEDULE_CALENDAR_LIST,
        'calendar'
    )


class TestSyncCompanyStatusesCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.company_api_get_company_statuses_call,
        fixtures.API_COMPANY_STATUS_LIST,
        'company_status',
    )


class TestSyncTerritoriesCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.system_api_get_territories_call,
        fixtures.API_SYSTEM_TERRITORY_LIST,
        'territory',
    )


class TestSyncCompaniesCommand(AbstractBaseSyncTest, TestCase):
    def setUp(self):
        super().setUp()
        fixture_utils.init_territories()

    args = (
        mocks.company_api_get_call,
        fixtures.API_COMPANY_LIST,
        'company',
    )


class TestSyncCompanyTypesCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.company_api_get_company_types_call,
        fixtures.API_COMPANY_TYPES_LIST,
        'company_type'
    )


class TestSyncTeamsCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.service_api_get_teams_call,
        fixtures.API_SERVICE_TEAM_LIST,
        'team',
    )

    def setUp(self):
        super().setUp()
        fixture_utils.init_boards()


class TestSyncBoardsCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.service_api_get_boards_call,
        fixtures.API_BOARD_LIST,
        'board',
    )


class TestSyncLocationsCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.service_api_get_locations_call,
        fixtures.API_SERVICE_LOCATION_LIST,
        'location',
    )


class TestSyncPrioritiesCommand(AbstractBaseSyncTest, TestCase):

    args = (
        mocks.service_api_get_priorities_call,
        fixtures.API_SERVICE_PRIORITY_LIST,
        'priority',
    )


class TestSyncProjectStatusesCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.projects_api_get_project_statuses_call,
        fixtures.API_PROJECT_STATUSES,
        'project_status',
    )


class TestSyncProjectsCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.project_api_get_projects_call,
        fixtures.API_PROJECT_LIST,
        'project',
    )

    def setUp(self):
        super().setUp()
        fixture_utils.init_project_statuses()


class TestSyncBoardsStatusesCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.service_api_get_statuses_call,
        fixtures.API_BOARD_STATUS_LIST,
        'board_status',
    )

    def setUp(self):
        board_synchronizer = sync.BoardSynchronizer()
        models.ConnectWiseBoard.objects.all().delete()
        _, _patch = mocks.service_api_get_boards_call(fixtures.API_BOARD_LIST)
        board_synchronizer.sync()
        _patch.stop()


class TestSyncSLAsCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.service_api_get_slas_call,
        fixtures.API_SERVICE_SLA_LIST,
        'sla',
    )

    def setUp(self):
        fixture_utils.init_calendars()


class TestSyncServiceNotesCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.service_api_get_notes_call,
        fixtures.API_SERVICE_NOTE_LIST,
        'service_note'
    )

    def setUp(self):
        super().setUp()
        fixture_utils.init_service_notes()
        fixture_utils.init_members()
        fixture_utils.init_territories()
        fixture_utils.init_companies()
        fixture_utils.init_boards()
        fixture_utils.init_board_statuses()
        fixture_utils.init_tickets()


class TestSyncOpportunityNotesCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.sales_api_get_opportunity_notes_call,
        fixtures.API_SALES_OPPORTUNITY_NOTE_LIST,
        'opportunity_note'
    )

    def setUp(self):
        super().setUp()
        fixture_utils.init_opportunity_statuses()
        fixture_utils.init_opportunity_types()
        fixture_utils.init_opportunities()
        fixture_utils.init_opportunity_notes()


class TestSyncOpportunityCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.sales_api_get_opportunities_call,
        [fixtures.API_SALES_OPPORTUNITY],
        'opportunity',
    )

    def setUp(self):
        super().setUp()
        fixture_utils.init_territories()
        fixture_utils.init_companies()
        fixture_utils.init_members()
        fixture_utils.init_opportunity_statuses()
        fixture_utils.init_opportunity_types()


class TestSyncOpportunityStatusesCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.sales_api_get_opportunity_statuses_call,
        fixtures.API_SALES_OPPORTUNITY_STATUSES,
        'opportunity_status',
    )


class TestSyncOpportunityTypesCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.sales_api_get_opportunity_types_call,
        fixtures.API_SALES_OPPORTUNITY_TYPES,
        'opportunity_type',
    )


class TestSyncSalesProbabilitiesCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.sales_api_get_sales_probabilities_call,
        fixtures.API_SALES_PROBABILITY_LIST,
        'sales_probability'
    )


class TestSyncTimeEntriesCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.time_api_get_time_entries_call,
        fixtures.API_TIME_ENTRY_LIST,
        'time_entry'
    )

    def setUp(self):
        super().setUp()
        fixture_utils.init_boards()
        fixture_utils.init_board_statuses()
        fixture_utils.init_tickets()
        fixture_utils.init_territories()
        fixture_utils.init_companies()
        fixture_utils.init_members()


class TestSyncScheduleEntriesCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.schedule_api_get_schedule_entries_call,
        fixtures.API_SCHEDULE_ENTRIES,
        'schedule_entry'
    )

    def setUp(self):
        super().setUp()
        fixture_utils.init_boards()
        fixture_utils.init_board_statuses()
        fixture_utils.init_territories()
        fixture_utils.init_companies()
        fixture_utils.init_locations()
        fixture_utils.init_teams()
        fixture_utils.init_members()
        fixture_utils.init_priorities()
        fixture_utils.init_projects()
        fixture_utils.init_schedule_types()
        fixture_utils.init_schedule_statuses()
        fixture_utils.init_tickets()


class TestSyncScheduleTypesCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.schedule_api_get_schedule_types_call,
        fixtures.API_SCHEDULE_TYPE_LIST,
        'schedule_type'
    )


class TestSyncScheduleStatusesCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.schedule_api_get_schedule_statuses_call,
        fixtures.API_SCHEDULE_STATUS_LIST,
        'schedule_status'
    )


@unittest.skip("Activities sync is temporarily removed- see issue #484")
class TestSyncActivityCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.sales_api_get_activities_call,
        fixtures.API_SALES_ACTIVITIES,
        'activity'
    )

    def setUp(self):
        super(). setUp()
        fixture_utils.init_territories()
        fixture_utils.init_companies()
        mocks.system_api_get_member_image_by_photo_id_call(
            (mocks.CW_MEMBER_IMAGE_FILENAME, mocks.get_member_avatar()))
        fixture_utils.init_members()
        fixture_utils.init_opportunity_statuses()
        fixture_utils.init_opportunity_types()
        fixture_utils.init_opportunities()
        fixture_utils.init_tickets()
        fixture_utils.init_board_statuses()
        fixture_utils.init_activities()


class TestSyncAllCommand(TestCase):

    def setUp(self):
        super().setUp()
        mocks.system_api_get_members_call([fixtures.API_MEMBER])
        mocks.system_api_get_member_image_by_photo_id_call(
            (mocks.CW_MEMBER_IMAGE_FILENAME, mocks.get_member_avatar()))
        mocks.company_api_by_id_call(fixtures.API_COMPANY)
        mocks.service_api_tickets_call()
        sync_test_cases = [
            TestSyncCompanyStatusesCommand,
            TestSyncCompaniesCommand,
            TestSyncCompanyTypesCommand,
            TestSyncLocationsCommand,
            TestSyncPrioritiesCommand,
            TestSyncProjectStatusesCommand,
            TestSyncProjectsCommand,
            TestSyncTeamsCommand,
            TestSyncBoardsStatusesCommand,
            TestSyncBoardsCommand,
            TestSyncServiceNotesCommand,
            TestSyncOpportunityNotesCommand,
            TestSyncOpportunityStatusesCommand,
            TestSyncOpportunityTypesCommand,
            TestSyncOpportunityCommand,
            TestSyncSalesProbabilitiesCommand,
            # TestSyncActivityCommand,
            TestSyncScheduleTypesCommand,
            TestSyncScheduleStatusesCommand,
            TestSyncScheduleEntriesCommand,
            TestSyncTimeEntriesCommand,
            TestSyncTerritoriesCommand,
            TestSyncSLAsCommand,
            TestSyncCalendarsCommand
        ]

        self.test_args = []

        for test_case in sync_test_cases:
            self.test_args.append(test_case.args)
            apicall, fixture, cw_object = test_case.args
            apicall(fixture)

    def _test_sync(self, full_option=False):
        out = io.StringIO()
        args = ['cwsync']

        if full_option:
            args.append('--full')

        call_command(*args, stdout=out)

        return out.getvalue().strip()

    def test_sync(self):
        """Test sync all objects command."""

        output = self._test_sync()
        for apicall, fixture, cw_object in self.test_args:
            summary = sync_summary(slug_to_title(cw_object), len(fixture))
            self.assertIn(summary, output)

        self.assertEqual(models.Team.objects.all().count(),
                         len(fixtures.API_SERVICE_TEAM_LIST))
        self.assertEqual(models.CompanyStatus.objects.all().count(),
                         len(fixtures.API_COMPANY_STATUS_LIST))

        self.assertEqual(models.TicketPriority.objects.all().count(),
                         len(fixtures.API_SERVICE_PRIORITY_LIST))
        self.assertEqual(models.ConnectWiseBoard.objects.all().count(),
                         len(fixtures.API_BOARD_LIST))
        self.assertEqual(models.BoardStatus.objects.all().count(),
                         len(fixtures.API_BOARD_STATUS_LIST))
        self.assertEqual(models.Location.objects.all().count(),
                         1)

        self.assertEqual(models.Ticket.objects.all().count(),
                         len([fixtures.API_SERVICE_TICKET]))

    def test_full_sync(self):
        """Test sync all objects command."""
        cw_object_map = {
            'member': models.Member,
            'board': models.ConnectWiseBoard,
            'priority': models.TicketPriority,
            'project_status': models.ProjectStatus,
            'project': models.Project,
            'board_status': models.BoardStatus,
            'territory': models.Territory,
            'company_status': models.CompanyStatus,
            'company_type': models.CompanyType,
            'team': models.Team,
            'location': models.Location,
            'ticket': models.Ticket,
            'service_note': models.ServiceNote,
            'opportunity_note': models.OpportunityNote,
            'company': models.Company,
            'opportunity': models.Opportunity,
            'opportunity_status': models.OpportunityStatus,
            'opportunity_type': models.OpportunityType,
            'sales_probability': models.SalesProbability,
            # 'activity': models.Activity,
            'schedule_entry': models.ScheduleEntry,
            'schedule_type': models.ScheduleType,
            'schedule_status': models.ScheduleStatus,
            'time_entry': models.TimeEntry,
            'sla': models.Sla,
            'calendar': models.Calendar
        }

        self.test_sync()

        fixture_utils.init_members()
        fixture_utils.init_board_statuses()
        fixture_utils.init_teams()

        pre_full_sync_counts = {}

        for key, clazz in cw_object_map.items():
            pre_full_sync_counts[key] = clazz.objects.all().count()

        mocks.system_api_get_members_call([])
        mocks.company_api_by_id_call([])

        for apicall, _, _ in self.test_args:
            apicall([])

        output = self._test_sync(full_option=True)

        for apicall, fixture, cw_object in self.test_args:
            summary = full_sync_summary(slug_to_title(cw_object),
                                        pre_full_sync_counts[cw_object])
            self.assertIn(summary, output)


class TestListCallBacksCommand(TestCase):

    def test_command(self):
        fixture = [fixtures.API_SYSTEM_CALLBACK_ENTRY]
        method = 'djconnectwise.callback.TicketCallBackHandler.get_callbacks'
        mocks.create_mock_call(method, fixture)

        out = io.StringIO()
        call_command('list_callbacks', stdout=out)

        fixtures.API_SYSTEM_CALLBACK_ENTRY
        output_str = out.getvalue().strip()
        self.assertIn(
            str(fixtures.API_SYSTEM_CALLBACK_ENTRY['id']),
            output_str)

        self.assertIn(
            str(fixtures.API_SYSTEM_CALLBACK_ENTRY['description']),
            output_str)


class TestCallBackCommand(TestCase):
    handlers = [
        callback.TicketCallBackHandler,
        callback.ProjectCallBackHandler,
        callback.CompanyCallBackHandler,
        callback.OpportunityCallBackHandler
    ]

    def get_fixture(self):
        fixture = fixtures.API_SYSTEM_CALLBACK_ENTRY
        fixture['type'] = self.handler.CALLBACK_TYPE
        return fixture

    def clean(self):
        models.CallBackEntry.objects.all().delete()

    def call(self, cmd, arg):
        out = io.StringIO()
        call_command(cmd, arg, stdout=out)
        return out.getvalue().strip()

    def _test_command(self, action, command, no_output=False):
        for handler in self.handlers:
            with transaction.atomic():
                self.clean()
                self.handler = handler()
                fixture = self.get_fixture()
                mocks.system_api_delete_callback_call({})
                mocks.system_api_create_callback_call(fixture)
                mocks.system_api_get_callbacks_call([fixture])

                callback_type = handler.CALLBACK_TYPE
                output = self.call(command, callback_type)

            if no_output:
                self.assertEqual('', output)
            else:
                expected = '{} {} callback'.format(action, callback_type)
                self.assertEqual(expected, output)

    def test_create_command(self):
        self._test_command('', 'create_callback', no_output=True)

    def test_delete_command(self):
        self._test_command('delete', 'delete_callback', no_output=True)
