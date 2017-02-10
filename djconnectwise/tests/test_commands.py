import io

from django.core.management import call_command
from django.test import TestCase

from djconnectwise.models import ConnectWiseBoard

from . import mocks
from . import fixtures
from .. import sync


class BaseSyncTest(TestCase):

    def _test_sync(self, mock_call, return_value, cw_object, msg):
        mock_call(return_value)
        out = io.StringIO()
        call_command('cwsync', cw_object, stdout=out)
        self.assertIn(msg, out.getvalue().strip())


class TestSyncCompaniesCommand(BaseSyncTest):

    def test_sync(self):
        " Test sync companies command."
        self._test_sync(mocks.company_api_get_call,
                        fixtures.API_COMPANY_LIST,
                        'company',
                        'Sync Summary - Created: 1 , Updated: 0')


class TestSyncBoardsCommand(BaseSyncTest):

    def test_sync(self):
        " Test sync boards command."
        self._test_sync(mocks.service_api_get_boards_call,
                        fixtures.API_BOARD_LIST,
                        'board',
                        'Sync Summary - Created: 1 , Updated: 0')


class TestSyncBoardsStatusesCommand(BaseSyncTest):

    def setUp(self):
        board_synchronizer = sync.BoardSynchronizer()
        ConnectWiseBoard.objects.all().delete()
        _, _patch = mocks.service_api_get_boards_call(fixtures.API_BOARD_LIST)
        board_synchronizer.sync()
        _patch.stop()

    def test_sync(self):
        " Test sync_board_statuses command."
        self._test_sync(mocks.service_api_get_statuses_call,
                        fixtures.API_BOARD_STATUS_LIST,
                        'board_status',
                        'Sync Summary - Created: 2 , Updated: 0')
