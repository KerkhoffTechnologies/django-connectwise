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


def init_projects():
    mocks.project_api_get_projects_call(fixtures.API_PROJECT_LIST)
    synchronizer = sync.ProjectSynchronizer()
    return synchronizer.sync()


def init_companies():
    mocks.company_api_get_call(fixtures.API_COMPANY_LIST)
    synchronizer = sync.CompanySynchronizer()
    return synchronizer.sync()
