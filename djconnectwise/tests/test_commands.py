import io

from django.core.management import call_command
from django.test import TestCase

from djconnectwise import models

from . import mocks
from . import fixtures
from . import fixture_utils


def sync_summary(class_name, created_count):
    return '{} Sync Summary - Created: {}, Updated: 0, Skipped: 0'.format(
        class_name, created_count
    )


def full_sync_summary(class_name, deleted_count):
    return '{} Sync Summary - Created: 0, Updated: 0, Skipped: 0, ' \
           'Deleted: {}'.format(class_name, deleted_count)


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
        msg_tmpl = '{} Sync Summary - Created: 0, Updated: 0, Skipped: 0, ' \
                   'Deleted: {}'
        msg = msg_tmpl.format(obj_label, len(return_value))
        self.assertEqual(msg, out.getvalue().strip())


class TestSyncCalendarsCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.schedule_api_get_calendars_call,
        fixtures.API_SCHEDULE_CALENDAR_LIST,
        'calendar'
    )

    def setUp(self):
        super().setUp()
        fixture_utils.init_holiday_lists()


class TestSyncHolidayCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.schedule_api_get_holidays_call,
        fixtures.API_SCHEDULE_HOLIDAY_MODEL_LIST,
        'holiday'
    )

    def setUp(self):
        fixture_utils.init_holiday_lists()


class TestSyncHolidayListCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.schedule_api_get_holiday_lists_call,
        fixtures.API_SCHEDULE_HOLIDAY_LIST_LIST,
        'holiday_list'
    )


class TestSyncTerritoriesCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.system_api_get_territories_call,
        fixtures.API_SYSTEM_TERRITORY_LIST,
        'territory',
    )


class TestSyncContactsCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.company_api_get_contacts,
        fixtures.API_COMPANY_CONTACT_LIST,
        'contact',
    )


class TestSyncCommunicationTypesCommand(AbstractBaseSyncTest, TestCase):
    def setUp(self):
        super().setUp()
        fixture_utils.init_communication_types()

    args = (
        mocks.company_api_get_communication_types,
        fixtures.API_COMMUNICATION_TYPE_LIST,
        'communication_type',
    )


class TestSyncContactCommunicationsCommand(AbstractBaseSyncTest, TestCase):
    def setUp(self):
        super().setUp()
        fixture_utils.init_territories()
        fixture_utils.init_company_statuses()
        fixture_utils.init_company_types()
        fixture_utils.init_companies()
        fixture_utils.init_communication_types()
        fixture_utils.init_contacts()

    args = (
        mocks.company_api_get_contact_communications,
        fixtures.API_CONTACT_COMMUNICATION_LIST,
        'contact_communication',
    )


class TestSyncCompaniesCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.company_api_get_call,
        fixtures.API_COMPANY_LIST,
        'company',
    )


class TestSyncCompanyStatusesCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.company_api_get_company_statuses_call,
        fixtures.API_COMPANY_STATUS_LIST,
        'company_status',
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
        fixture_utils.init_work_roles()
        fixture_utils.init_work_types()
        fixture_utils.init_boards()


class TestSyncBoardsCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.service_api_get_boards_call,
        fixtures.API_BOARD_LIST,
        'board',
    )

    def setUp(self):
        super().setUp()
        fixture_utils.init_work_types()
        fixture_utils.init_work_roles()


class TestSyncLocationsCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.service_api_get_locations_call,
        fixtures.API_SERVICE_LOCATION_LIST,
        'location',
    )


class TestSyncMyCompanyOtherCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.system_api_get_other_call,
        fixtures.API_SYSTEM_OTHER_LIST,
        'company_other',
    )

    def setUp(self):
        fixture_utils.init_holiday_lists()
        fixture_utils.init_calendars()


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


class TestSyncProjectTypesCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.projects_api_get_project_types_call,
        fixtures.API_PROJECT_TYPES,
        'project_type',
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


class TestSyncProjectPhaseCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.projects_api_get_project_phases_call,
        fixtures.API_PROJECT_PHASE_LIST,
        'project_phase'
    )

    def setUp(self):
        super().setUp()
        mocks.system_api_get_member_image_by_photo_id_call(
            (mocks.CW_MEMBER_IMAGE_FILENAME, mocks.get_member_avatar()))
        fixture_utils.init_members()
        fixture_utils.init_territories()
        fixture_utils.init_company_statuses()
        fixture_utils.init_company_types()
        fixture_utils.init_companies()
        fixture_utils.init_project_types()
        fixture_utils.init_project_statuses()
        fixture_utils.init_projects()


class TestSyncProjectTeamMemberCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.project_api_get_team_members_call,
        fixtures.API_PROJECT_TEAM_MEMBER_LIST,
        'project_team_member'
    )

    def setUp(self):
        super().setUp()
        mocks.system_api_get_member_image_by_photo_id_call(
            (mocks.CW_MEMBER_IMAGE_FILENAME, mocks.get_member_avatar()))
        fixture_utils.init_members()
        fixture_utils.init_work_roles()
        fixture_utils.init_work_types()
        fixture_utils.init_territories()
        fixture_utils.init_company_statuses()
        fixture_utils.init_company_types()
        fixture_utils.init_companies()
        fixture_utils.init_project_types()
        fixture_utils.init_project_statuses()
        fixture_utils.init_projects()
        fixture_utils.init_boards()


class TestSyncBoardsStatusesCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.service_api_get_statuses_call,
        fixtures.API_BOARD_STATUS_LIST,
        'board_status',
    )

    def setUp(self):
        super().setUp()
        fixture_utils.init_work_roles()
        fixture_utils.init_work_types()
        fixture_utils.init_boards()


class TestSyncSLAsCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.service_api_get_slas_call,
        fixtures.API_SERVICE_SLA_LIST,
        'sla',
    )

    def setUp(self):
        fixture_utils.init_calendars()


class TestSyncSLAPrioritiesCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.service_api_get_sla_priorities_call,
        fixtures.API_SERVICE_SLA_PRIORITY_LIST,
        'sla_priority'
    )

    def setUp(self):
        fixture_utils.init_holiday_lists()
        fixture_utils.init_calendars()
        fixture_utils.init_slas()
        fixture_utils.init_priorities()


class TestSyncServiceNotesCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.service_api_get_notes_call,
        fixtures.API_SERVICE_NOTE_LIST,
        'service_note'
    )

    def setUp(self):
        super().setUp()
        mocks.system_api_get_member_image_by_photo_id_call(
            (mocks.CW_MEMBER_IMAGE_FILENAME, mocks.get_member_avatar()))
        fixture_utils.init_members()
        fixture_utils.init_work_roles()
        fixture_utils.init_work_types()
        fixture_utils.init_holiday_lists()
        fixture_utils.init_calendars()
        fixture_utils.init_slas()
        fixture_utils.init_locations()
        fixture_utils.init_territories()
        fixture_utils.init_company_statuses()
        fixture_utils.init_company_types()
        fixture_utils.init_companies()
        fixture_utils.init_contacts()
        fixture_utils.init_board_statuses()
        fixture_utils.init_teams()
        fixture_utils.init_types()
        fixture_utils.init_subtypes()
        fixture_utils.init_items()
        fixture_utils.init_priorities()
        fixture_utils.init_tickets()


class TestSyncOpportunityNotesCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.sales_api_get_opportunity_notes_call,
        fixtures.API_SALES_OPPORTUNITY_NOTE_LIST,
        'opportunity_note'
    )

    def setUp(self):
        super().setUp()
        mocks.system_api_get_member_image_by_photo_id_call(
            (mocks.CW_MEMBER_IMAGE_FILENAME, mocks.get_member_avatar()))
        fixture_utils.init_members()
        fixture_utils.init_sales_probabilities()
        fixture_utils.init_opportunity_statuses()
        fixture_utils.init_opportunity_stages()
        fixture_utils.init_opportunity_types()
        fixture_utils.init_opportunities()


class TestSyncOpportunityCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.sales_api_get_opportunities_call,
        [fixtures.API_SALES_OPPORTUNITY],
        'opportunity',
    )

    def setUp(self):
        super().setUp()
        mocks.system_api_get_member_image_by_photo_id_call(
            (mocks.CW_MEMBER_IMAGE_FILENAME, mocks.get_member_avatar()))
        fixture_utils.init_members()
        fixture_utils.init_territories()
        fixture_utils.init_company_statuses()
        fixture_utils.init_company_types()
        fixture_utils.init_companies()
        fixture_utils.init_contacts()
        fixture_utils.init_opportunity_statuses()
        fixture_utils.init_opportunity_stages()
        fixture_utils.init_opportunity_types()
        fixture_utils.init_sales_probabilities()


class TestSyncOpportunityStagesCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.sales_api_get_opportunity_stages_call,
        fixtures.API_SALES_OPPORTUNITY_STAGES,
        'opportunity_stage'
    )


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
        mocks.system_api_get_member_image_by_photo_id_call(
            (mocks.CW_MEMBER_IMAGE_FILENAME, mocks.get_member_avatar()))
        fixture_utils.init_members()
        fixture_utils.init_work_roles()
        fixture_utils.init_work_types()
        fixture_utils.init_holiday_lists()
        fixture_utils.init_calendars()
        fixture_utils.init_slas()
        fixture_utils.init_locations()
        fixture_utils.init_territories()
        fixture_utils.init_company_statuses()
        fixture_utils.init_company_types()
        fixture_utils.init_companies()
        fixture_utils.init_contacts()
        fixture_utils.init_board_statuses()
        fixture_utils.init_teams()
        fixture_utils.init_types()
        fixture_utils.init_subtypes()
        fixture_utils.init_items()
        fixture_utils.init_priorities()
        fixture_utils.init_tickets()


class TestSyncScheduleEntriesCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.schedule_api_get_schedule_entries_call,
        fixtures.API_SCHEDULE_ENTRIES,
        'schedule_entry'
    )

    def setUp(self):
        super().setUp()
        mocks.system_api_get_member_image_by_photo_id_call(
            (mocks.CW_MEMBER_IMAGE_FILENAME, mocks.get_member_avatar()))
        fixture_utils.init_members()
        fixture_utils.init_work_roles()
        fixture_utils.init_work_types()
        fixture_utils.init_holiday_lists()
        fixture_utils.init_calendars()
        fixture_utils.init_slas()
        fixture_utils.init_locations()
        fixture_utils.init_territories()
        fixture_utils.init_company_statuses()
        fixture_utils.init_company_types()
        fixture_utils.init_companies()
        fixture_utils.init_contacts()
        fixture_utils.init_board_statuses()
        fixture_utils.init_teams()
        fixture_utils.init_types()
        fixture_utils.init_subtypes()
        fixture_utils.init_items()
        fixture_utils.init_priorities()
        fixture_utils.init_tickets()
        fixture_utils.init_schedule_types()
        fixture_utils.init_schedule_statuses()


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


class TestSyncActivityStatusesCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.sales_api_get_activities_statuses_call,
        fixtures.API_SALES_ACTIVITY_STATUSES,
        'activity_status',
    )


class TestSyncActivityTypesCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.sales_api_get_activities_types_call,
        fixtures.API_SALES_ACTIVITY_TYPES,
        'activity_type',
    )


class TestSyncActivityCommand(AbstractBaseSyncTest, TestCase):
    args = (
        mocks.sales_api_get_activities_call,
        fixtures.API_SALES_ACTIVITIES,
        'activity'
    )

    def setUp(self):
        super().setUp()
        mocks.system_api_get_member_image_by_photo_id_call(
            (mocks.CW_MEMBER_IMAGE_FILENAME, mocks.get_member_avatar()))
        fixture_utils.init_members()
        fixture_utils.init_work_roles()
        fixture_utils.init_work_types()
        fixture_utils.init_territories()
        fixture_utils.init_company_statuses()
        fixture_utils.init_company_types()
        fixture_utils.init_companies()
        fixture_utils.init_contacts()
        fixture_utils.init_opportunity_statuses()
        fixture_utils.init_agreements()
        fixture_utils.init_sales_probabilities()
        fixture_utils.init_opportunity_types()
        fixture_utils.init_opportunity_stages()
        fixture_utils.init_opportunity_statuses()
        fixture_utils.init_opportunities()
        fixture_utils.init_activity_types()
        fixture_utils.init_activity_statuses()


class TestSyncTypeCommand(AbstractBaseSyncTest, TestCase):

    def setUp(self):
        super().setUp()
        fixture_utils.init_work_roles()
        fixture_utils.init_work_types()
        fixture_utils.init_boards()

    args = (
        mocks.service_api_get_types_call,
        fixtures.API_TYPE_LIST,
        'type'
    )


class TestSyncSubTypeCommand(AbstractBaseSyncTest, TestCase):
    def setUp(self):
        super().setUp()
        fixture_utils.init_work_roles()
        fixture_utils.init_work_types()
        fixture_utils.init_boards()

    args = (
        mocks.service_api_get_subtypes_call,
        fixtures.API_SUBTYPE_LIST,
        'sub_type'
    )


class TestSyncItemCommand(AbstractBaseSyncTest, TestCase):
    def setUp(self):
        super().setUp()
        fixture_utils.init_work_roles()
        fixture_utils.init_work_types()
        fixture_utils.init_boards()

    args = (
        mocks.service_api_get_items_call,
        fixtures.API_ITEM_LIST,
        'item'
    )


class TestSyncTypeSubTypeItemAssociationCommand(AbstractBaseSyncTest,
                                                TestCase):
    def setUp(self):
        super().setUp()
        fixture_utils.init_work_roles()
        fixture_utils.init_work_types()
        fixture_utils.init_boards()
        fixture_utils.init_teams()
        fixture_utils.init_types()
        fixture_utils.init_subtypes()
        fixture_utils.init_items()

    args = (
        mocks.service_api_get_type_subtype_item_associations_call,
        fixtures.API_TYPE_SUBTYPE_ITEM_ASSOCIATION_LIST,
        'type_subtype_item_association'
    )


class TestSyncWorkTypeCommand(AbstractBaseSyncTest, TestCase):
    def setUp(self):
        super().setUp()
        fixture_utils.init_work_types()

    args = (
        mocks.time_api_get_work_types_call,
        fixtures.API_WORK_TYPE_LIST,
        'work_type'
    )


class TestSyncWorkRoleCommand(AbstractBaseSyncTest, TestCase):
    def setUp(self):
        super().setUp()
        fixture_utils.init_work_roles()

    args = (
        mocks.time_api_get_work_roles_call,
        fixtures.API_WORK_ROLE_LIST,
        'work_role'
    )


class TestSyncAgreementCommand(AbstractBaseSyncTest, TestCase):
    def setUp(self):
        super().setUp()
        fixture_utils.init_work_roles()
        fixture_utils.init_work_types()
        fixture_utils.init_territories()
        fixture_utils.init_company_statuses()
        fixture_utils.init_company_types()
        fixture_utils.init_companies()

    args = (
        mocks.finance_api_get_agreements_call,
        fixtures.API_AGREEMENT_LIST,
        'agreement'
    )


class TestSyncProjectTicketCommand(AbstractBaseSyncTest, TestCase):
    def setUp(self):
        super().setUp()
        mocks.system_api_get_member_image_by_photo_id_call(
            (mocks.CW_MEMBER_IMAGE_FILENAME, mocks.get_member_avatar()))
        fixture_utils.init_members()
        fixture_utils.init_work_roles()
        fixture_utils.init_work_types()
        fixture_utils.init_locations()
        fixture_utils.init_territories()
        fixture_utils.init_company_statuses()
        fixture_utils.init_company_types()
        fixture_utils.init_companies()
        fixture_utils.init_contacts()
        fixture_utils.init_board_statuses()
        fixture_utils.init_teams()
        fixture_utils.init_types()
        fixture_utils.init_subtypes()
        fixture_utils.init_items()
        fixture_utils.init_priorities()
        fixture_utils.init_project_types()
        fixture_utils.init_project_statuses()
        fixture_utils.init_projects()

    args = (
        mocks.project_api_tickets_test_command,
        fixtures.API_PROJECT_TICKET_LIST,
        'project_ticket'
    )


class TestSyncAllCommand(TestCase):

    def setUp(self):
        super().setUp()
        mocks.system_api_get_members_call([fixtures.API_MEMBER])
        mocks.system_api_get_member_image_by_photo_id_call(
            (mocks.CW_MEMBER_IMAGE_FILENAME, mocks.get_member_avatar()))
        mocks.company_api_by_id_call(fixtures.API_COMPANY)
        mocks.service_api_tickets_call()
        sync_test_cases = [
            TestSyncTimeEntriesCommand,
            TestSyncContactCommunicationsCommand,
            TestSyncContactsCommand,
            TestSyncCommunicationTypesCommand,
            TestSyncCompaniesCommand,
            TestSyncCompanyTypesCommand,
            TestSyncCompanyStatusesCommand,
            TestSyncLocationsCommand,
            TestSyncPrioritiesCommand,
            TestSyncProjectPhaseCommand,
            TestSyncProjectStatusesCommand,
            TestSyncProjectsCommand,
            TestSyncTeamsCommand,
            TestSyncBoardsStatusesCommand,
            TestSyncBoardsCommand,
            TestSyncServiceNotesCommand,
            TestSyncOpportunityNotesCommand,
            TestSyncOpportunityStatusesCommand,
            TestSyncOpportunityStagesCommand,
            TestSyncOpportunityTypesCommand,
            TestSyncOpportunityCommand,
            TestSyncSalesProbabilitiesCommand,
            TestSyncActivityStatusesCommand,
            TestSyncActivityTypesCommand,
            TestSyncActivityCommand,
            TestSyncScheduleTypesCommand,
            TestSyncScheduleStatusesCommand,
            TestSyncScheduleEntriesCommand,
            TestSyncTerritoriesCommand,
            TestSyncSLAsCommand,
            TestSyncCalendarsCommand,
            TestSyncSLAPrioritiesCommand,
            TestSyncMyCompanyOtherCommand,
            TestSyncHolidayCommand,
            TestSyncHolidayListCommand,
            TestSyncTypeCommand,
            TestSyncSubTypeCommand,
            TestSyncItemCommand,
            TestSyncTypeSubTypeItemAssociationCommand,
            TestSyncWorkTypeCommand,
            TestSyncWorkRoleCommand,
            TestSyncAgreementCommand,
            TestSyncProjectTypesCommand,
            TestSyncProjectTeamMemberCommand
        ]

        self.test_args = []

        for test_case in sync_test_cases:
            self.test_args.append(test_case.args)
            apicall, fixture, cw_object = test_case.args
            apicall(fixture)

    def run_sync_command(self, full_option=False):
        out = io.StringIO()
        args = ['cwsync']

        if full_option:
            args.append('--full')

        call_command(*args, stdout=out)

        return out.getvalue().strip()

    def test_partial_sync(self):
        """
        Test the command to run a sync of all objects without
        the --full argument.
        """
        output = self.run_sync_command()

        for apicall, fixture, cw_object in self.test_args:
            summary = sync_summary(slug_to_title(cw_object), len(fixture))
            self.assertIn(summary, output)

        self.assertEqual(models.Team.objects.all().count(),
                         len(fixtures.API_SERVICE_TEAM_LIST))
        self.assertEqual(models.Contact.objects.all().count(),
                         len(fixtures.API_COMPANY_CONTACT_LIST))
        self.assertEqual(models.ContactCommunication.objects.all().count(),
                         len(fixtures.API_CONTACT_COMMUNICATION_LIST))
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
        """Test the command to run a full sync of all objects."""
        cw_object_map = {
            'member': models.Member,
            'board': models.ConnectWiseBoard,
            'priority': models.TicketPriority,
            'project_status': models.ProjectStatus,
            'project': models.Project,
            'project_phase': models.ProjectPhase,
            'board_status': models.BoardStatus,
            'territory': models.Territory,
            'company_status': models.CompanyStatus,
            'company_type': models.CompanyType,
            'team': models.Team,
            'location': models.Location,
            'ticket': models.Ticket,
            'service_note': models.ServiceNote,
            'opportunity_note': models.OpportunityNote,
            'contact': models.Contact,
            'communication_type': models.CommunicationType,
            'contact_communication': models.ContactCommunication,
            'company': models.Company,
            'opportunity': models.Opportunity,
            'opportunity_status': models.OpportunityStatus,
            'opportunity_stage': models.OpportunityStage,
            'opportunity_type': models.OpportunityType,
            'sales_probability': models.SalesProbability,
            'activity_status': models.ActivityStatus,
            'activity_type': models.ActivityType,
            'activity': models.Activity,
            'schedule_entry': models.ScheduleEntry,
            'schedule_type': models.ScheduleType,
            'schedule_status': models.ScheduleStatus,
            'time_entry': models.TimeEntry,
            'sla': models.Sla,
            'calendar': models.Calendar,
            'sla_priority': models.SlaPriority,
            'company_other': models.MyCompanyOther,
            'holiday': models.Holiday,
            'holiday_list': models.HolidayList,
            'type': models.Type,
            'sub_type': models.SubType,
            'item': models.Item,
            'type_subtype_item_association': models.TypeSubTypeItemAssociation,
            'work_type': models.WorkType,
            'work_role': models.WorkRole,
            'agreement': models.Agreement,
            'project_type': models.ProjectType,
            'project_team_member': models.ProjectTeamMember,
        }

        # Run partial sync first
        self.run_sync_command()

        fixture_utils.init_projects()
        fixture_utils.init_members()
        fixture_utils.init_board_statuses()
        fixture_utils.init_teams()

        pre_full_sync_counts = {}

        for key, model_class in cw_object_map.items():
            pre_full_sync_counts[key] = model_class.objects.all().count()

        mocks.system_api_get_members_call([])
        mocks.company_api_by_id_call([])

        for apicall, _, _ in self.test_args:
            apicall([])

        output = self.run_sync_command(full_option=True)

        for apicall, fixture, cw_object in self.test_args:
            if cw_object in (
                    'team',
                    'service_note',
                    'opportunity_note',
                    'sla_priority',
                    'holiday',
            ):
                # Assert that there were objects to get deleted, then change
                # to zero to verify the output formats correctly.
                # We are just testing the command, there are sync tests to
                # verify that the syncronizers work correctly
                self.assertGreater(pre_full_sync_counts[cw_object], 0)
                pre_full_sync_counts[cw_object] = 0
            summary = full_sync_summary(
                slug_to_title(cw_object),
                pre_full_sync_counts[cw_object]
            )
            self.assertIn(summary, output)


class TestListUsersCommand(TestCase):
    def test_command(self):
        # We don't need to check output carefully. Just verify it
        # doesn't explode.
        self.assertEqual(
            call_command('list_users'),
            None
        )
