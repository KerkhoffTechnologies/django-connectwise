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
    mocks.service_api_tickets_call()
    synchronizer = sync.TicketSynchronizer()
    return synchronizer.sync()


def init_priorities():
    mocks.service_api_get_priorities_call([fixtures.API_SERVICE_PRIORITY])
    synchronizer = sync.PrioritySynchronizer()
    return synchronizer.sync()


def init_projects():
    mocks.project_api_get_projects_call(fixtures.API_PROJECT_LIST)
    synchronizer = sync.ProjectSynchronizer()
    return synchronizer.sync()


def init_companies():
    mocks.company_api_get_call(fixtures.API_COMPANY_LIST)
    synchronizer = sync.CompanySynchronizer()
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


def init_opportunity_types():
    mocks.sales_api_get_opportunity_types_call(
        fixtures.API_SALES_OPPORTUNITY_TYPES)
    synchronizer = sync.OpportunityTypeSynchronizer()
    return synchronizer.sync()


def init_schedule_types():
    mocks.schedule_api_get_schedule_types_call(
        fixtures.API_SCHEDULE_TYPE_LIST)
    synchronizer = sync.ScheduleTypeSychronizer()
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
