from . import fixtures
from . import mocks
from djconnectwise import models
from djconnectwise import sync


def init_boards():
    """
    Initializes local board instances from fixture data
    """
    models.ConnectWiseBoard.objects.all().delete()
    mocks.service_api_get_boards_call(fixtures.API_BOARD_LIST)
    board_synchronizer = sync.BoardSynchronizer()
    board_synchronizer.sync()
