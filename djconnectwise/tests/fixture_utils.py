from . import fixtures
from . import mocks
from djconnectwise import models
from djconnectwise import sync


def init_boards():
    """
    Initialize local board instances from fixture data.
    """
    models.ConnectWiseBoard.objects.all().delete()
    mocks.service_api_get_boards_call(fixtures.API_BOARD_LIST)
    synchronizer = sync.BoardSynchronizer()
    return synchronizer.sync()


def init_board_statuses():
    init_boards()
    mocks.service_api_get_statuses_call(fixtures.API_BOARD_STATUS_LIST)
    synchronizer = sync.BoardStatusSynchronizer()
    return synchronizer.sync()


def init_teams():
    models.Team.objects.all().delete()
    mocks.service_api_get_teams_call(fixtures.API_SERVICE_TEAM_LIST)
    synchronizer = sync.TeamSynchronizer()
    return synchronizer.sync()


def init_members():
    models.Member.objects.all().delete()
    mocks.system_api_get_members_call(fixtures.API_MEMBER_LIST)
    synchronizer = sync.MemberSynchronizer()
    return synchronizer.sync()


def init_tickets():
    models.Ticket.objects.all().delete()
    mocks.service_api_tickets_call()
    synchronizer = sync.ServiceTicketSynchronizer()
    return synchronizer.sync()


def init_project_tickets():
    mocks.project_api_tickets_call()
    synchronizer = sync.ProjectTicketSynchronizer()
    return synchronizer.sync()


def init_service_notes():
    models.ServiceNote.objects.all().delete()
    mocks.service_api_get_notes_call(fixtures.API_SERVICE_NOTE_LIST)
    synchronizer = sync.ServiceNoteSynchronizer()
    return synchronizer.sync()


def init_opportunity_notes():
    mocks.sales_api_get_opportunity_notes_call(
        fixtures.API_SALES_OPPORTUNITY_NOTE_LIST
    )
    synchronizer = sync.OpportunityNoteSynchronizer()
    return synchronizer.sync()


def init_slas():
    mocks.service_api_get_slas_call(fixtures.API_SERVICE_SLA_LIST)
    synchronizer = sync.SLASynchronizer()
    return synchronizer.sync()


def init_slapriorities():
    mocks.service_api_get_sla_priorities_call(
        fixtures.API_SERVICE_SLA_PRIORITY_LIST
    )
    synchronizer = sync.SLAPrioritySynchronizer()
    return synchronizer.sync()


def init_calendars():
    mocks.schedule_api_get_calendars_call(fixtures.API_SCHEDULE_CALENDAR_LIST)
    synchronizer = sync.CalendarSynchronizer()
    return synchronizer.sync()


def init_holidays():
    mocks.schedule_api_get_holidays_call(
        fixtures.API_SCHEDULE_HOLIDAY_MODEL_LIST)
    synchronizer = sync.HolidaySynchronizer()
    return synchronizer.sync()


def init_holiday_lists():
    mocks.schedule_api_get_holiday_lists_call(
        fixtures.API_SCHEDULE_HOLIDAY_LIST_LIST)
    synchronizer = sync.HolidayListSynchronizer()
    return synchronizer.sync()


def init_others():
    mocks.system_api_get_other_call(fixtures.API_SYSTEM_OTHER_LIST)
    synchronizer = sync.MyCompanyOtherSynchronizer()
    return synchronizer.sync()


def init_priorities():
    mocks.service_api_get_priorities_call([fixtures.API_SERVICE_PRIORITY])
    synchronizer = sync.PrioritySynchronizer()
    return synchronizer.sync()


def init_project_statuses():
    mocks.projects_api_get_project_statuses_call(
        fixtures.API_PROJECT_STATUSES)
    synchronizer = sync.ProjectStatusSynchronizer()
    return synchronizer.sync()


def init_project_types():
    mocks.projects_api_get_project_types_call(
        fixtures.API_PROJECT_TYPES)
    synchronizer = sync.ProjectTypeSynchronizer()
    return synchronizer.sync()


def init_project_phases():
    mocks.projects_api_get_project_phases_call(
        fixtures.API_PROJECT_PHASE_LIST)
    synchronizer = sync.ProjectPhaseSynchronizer()
    return synchronizer.sync()


def init_projects():
    mocks.project_api_get_projects_call(fixtures.API_PROJECT_LIST)
    synchronizer = sync.ProjectSynchronizer()
    return synchronizer.sync()


def init_territories():
    mocks.system_api_get_territories_call(fixtures.API_SYSTEM_TERRITORY_LIST)
    synchronizer = sync.TerritorySynchronizer()
    return synchronizer.sync()


def init_contacts():
    mocks.company_api_get_contacts(fixtures.API_COMPANY_CONTACT_LIST)
    synchronizer = sync.ContactSynchronizer()
    return synchronizer.sync()


def init_contact_communications():
    mocks.company_api_get_contact_communications(
        fixtures.API_CONTACT_COMMUNICATION_LIST)
    synchronizer = sync.ContactCommunicationSynchronizer()
    return synchronizer.sync()


def init_companies():
    mocks.company_api_get_call(fixtures.API_COMPANY_LIST)
    synchronizer = sync.CompanySynchronizer()
    return synchronizer.sync()


def init_company_types():
    mocks.company_api_get_company_types_call(fixtures.API_COMPANY_TYPES_LIST)
    synchronizer = sync.CompanyTypeSynchronizer()
    return synchronizer.sync()


def init_locations():
    mocks.service_api_get_locations_call(fixtures.API_SERVICE_LOCATION_LIST)
    synchronizer = sync.LocationSynchronizer()
    return synchronizer.sync()


def init_opportunity_statuses():
    mocks.sales_api_get_opportunity_statuses_call(
        fixtures.API_SALES_OPPORTUNITY_STATUSES)
    synchronizer = sync.OpportunityStatusSynchronizer()
    return synchronizer.sync()


def init_sales_probabilities():
    mocks.sales_api_get_sales_probabilities_call(
        fixtures.API_SALES_PROBABILITY_LIST)
    synchronizer = sync.SalesProbabilitySynchronizer()
    return synchronizer.sync()


def init_opportunity_types():
    mocks.sales_api_get_opportunity_types_call(
        fixtures.API_SALES_OPPORTUNITY_TYPES)
    synchronizer = sync.OpportunityTypeSynchronizer()
    return synchronizer.sync()


def init_opportunity_stages():
    mocks.sales_api_get_opportunity_stages_call(
        fixtures.API_SALES_OPPORTUNITY_STAGES)
    synchronizer = sync.OpportunityStageSynchronizer()
    return synchronizer.sync()


def init_opportunities():
    mocks.sales_api_get_opportunities_call(
        fixtures.API_SALES_OPPORTUNITIES)
    synchronizer = sync.OpportunitySynchronizer()
    return synchronizer.sync()


def init_schedule_types():
    mocks.schedule_api_get_schedule_types_call(
        fixtures.API_SCHEDULE_TYPE_LIST)
    synchronizer = sync.ScheduleTypeSynchronizer()
    return synchronizer.sync()


def init_schedule_statuses():
    mocks.schedule_api_get_schedule_statuses_call(
        fixtures.API_SCHEDULE_STATUS_LIST)
    synchronizer = sync.ScheduleStatusSynchronizer()
    return synchronizer.sync()


def init_schedule_entries():
    mocks.schedule_api_get_schedule_entries_call(
        fixtures.API_SCHEDULE_ENTRIES)
    synchronizer = sync.ScheduleEntriesSynchronizer()
    return synchronizer.sync()


def init_activity_statuses():
    mocks.sales_api_get_activities_statuses_call(
        fixtures.API_SALES_ACTIVITY_STATUSES)
    synchronizer = sync.ActivityStatusSynchronizer()
    return synchronizer.sync()


def init_activity_types():
    mocks.sales_api_get_activities_types_call(
        fixtures.API_SALES_ACTIVITY_TYPES)
    synchronizer = sync.ActivityTypeSynchronizer()
    return synchronizer.sync()


def init_activities():
    mocks.sales_api_get_activities_call(
        fixtures.API_SALES_ACTIVITIES)
    synchronizer = sync.ActivitySynchronizer()
    return synchronizer.sync()


def init_time_entries():
    mocks.time_api_get_time_entries_call(
        fixtures.API_TIME_ENTRY_LIST)
    synchronizer = sync.TimeEntrySynchronizer()
    return synchronizer.sync()


def init_types():
    mocks.service_api_get_types_call(
        fixtures.API_TYPE_LIST)
    synchronizer = sync.TypeSynchronizer()
    return synchronizer.sync()


def init_subtypes():
    mocks.service_api_get_subtypes_call(
        fixtures.API_SUBTYPE_LIST)
    synchronizer = sync.SubTypeSynchronizer()
    return synchronizer.sync()


def init_items():
    mocks.service_api_get_items_call(
        fixtures.API_ITEM_LIST)
    synchronizer = sync.ItemSynchronizer()
    return synchronizer.sync()


def init_work_types():
    mocks.time_api_get_work_types_call(
        fixtures.API_WORK_TYPE_LIST)
    synchronizer = sync.WorkTypeSynchronizer()
    return synchronizer.sync()


def init_work_roles():
    mocks.time_api_get_work_roles_call(
        fixtures.API_WORK_ROLE_LIST)
    synchronizer = sync.WorkRoleSynchronizer()
    return synchronizer.sync()


def init_agreements():
    mocks.finance_api_get_agreements_call(
        fixtures.API_AGREEMENT_LIST)
    synchronizer = sync.AgreementSynchronizer()
    return synchronizer.sync()


def init_project_team_members():
    mocks.project_api_get_team_members_call(
        fixtures.API_PROJECT_TEAM_MEMBER_LIST)
    synchronizer = sync.ProjectTeamMemberSynchronizer()
    return synchronizer
