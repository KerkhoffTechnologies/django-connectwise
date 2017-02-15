import io

from django.core.management import call_command
from django.test import TestCase

from djconnectwise.models import ConnectWiseBoard

from . import mocks
from . import fixtures
from .. import sync


class BaseSyncTest(TestCase):

    BOARD_SYNC_SUMMARY = 'Board Sync Summary - Created: 1 , Updated: 0'
    COMPANY_SYNC_SUMMARY = 'Company Sync Summary - Created: 1 , Updated: 0'
    STATUS_SYNC_SUMMARY = 'Board Status Sync Summary - Created: 2 , Updated: 0'
    MEMBER_SYNC_SUMMARY = 'Member Sync Summary - Created: 1 , Updated: 0'
    TICKET_SYNC_SUMMARY = 'Ticket Sync Summary - Created: 1 , Updated: 0'
    PRIORITY_SYNC_SUMMARY = 'Priority Sync Summary - Created: 1 , Updated: 0'

    def _test_sync(self, mock_call, return_value, cw_object, msg):
        mock_call(return_value)
        out = io.StringIO()
        call_command('cwsync', cw_object, stdout=out)
        self.assertIn(msg, out.getvalue().strip())


class TestSyncCompaniesCommand(BaseSyncTest):

    def test_sync(self):
        "Test sync companies command."
        self._test_sync(mocks.company_api_get_call,
                        fixtures.API_COMPANY_LIST,
                        'company',
                        self.COMPANY_SYNC_SUMMARY
                        )


class TestSyncBoardsCommand(BaseSyncTest):

    def test_sync(self):
        "Test sync boards command."
        self._test_sync(mocks.service_api_get_boards_call,
                        fixtures.API_BOARD_LIST,
                        'board',
                        self.BOARD_SYNC_SUMMARY)


class TestSyncPrioritiesCommand(BaseSyncTest):

    def test_sync(self):
        "Test sync priorities command."
        self._test_sync(mocks.service_api_get_priorities_call,
                        fixtures.API_SERVICE_PRIORITY_LIST,
                        'priority',
                        self.PRIORITY_SYNC_SUMMARY)


class TestSyncBoardsStatusesCommand(BaseSyncTest):

    def setUp(self):
        board_synchronizer = sync.BoardSynchronizer()
        ConnectWiseBoard.objects.all().delete()
        _, _patch = mocks.service_api_get_boards_call(fixtures.API_BOARD_LIST)
        board_synchronizer.sync()
        _patch.stop()

    def test_sync(self):
        "Test sync_board_statuses command."
        self._test_sync(mocks.service_api_get_statuses_call,
                        fixtures.API_BOARD_STATUS_LIST,
                        'board_status',
                        self.STATUS_SYNC_SUMMARY
                        )


class TestSyncAllCommand(BaseSyncTest):
    def test_sync(self):
        "Test sync all objects command."
        mocks.company_api_get_call(fixtures.API_COMPANY_LIST)
        mocks.service_api_get_boards_call(fixtures.API_BOARD_LIST)
        mocks.service_api_get_statuses_call(fixtures.API_BOARD_STATUS_LIST)
        mocks.system_api_get_members_call([fixtures.API_MEMBER])
        mocks.system_api_get_member_image_by_identifier_call(
            (mocks.CW_MEMBER_IMAGE_FILENAME, mocks.get_member_avatar()))
        mocks.company_api_by_id_call(fixtures.API_COMPANY)
        mocks.service_api_tickets_call()
        mocks.service_api_get_priorities_call(
            fixtures.API_SERVICE_PRIORITY_LIST)

        out = io.StringIO()
        call_command('cwsync', stdout=out)
        actual_output = out.getvalue().strip()

        summaries = [
            self.BOARD_SYNC_SUMMARY,
            self.COMPANY_SYNC_SUMMARY,
            self.STATUS_SYNC_SUMMARY,
            self.MEMBER_SYNC_SUMMARY,
            self.TICKET_SYNC_SUMMARY]

        for summary in summaries:
            self.assertIn(summary, actual_output)
