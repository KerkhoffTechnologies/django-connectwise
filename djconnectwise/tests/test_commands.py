import io

from django.core.management import call_command
from django.test import TestCase

from djconnectwise.models import ConnectWiseBoard

from . import mocks
from . import fixtures
from . import fixture_utils
from .. import sync


def sync_summary(class_name):
    created_count = 2 if class_name in ['Priority', 'Board Status'] else 1
    return '{} Sync Summary - Created: {} , Updated: 0'.format(
        class_name, created_count
    )


class BaseSyncTest(TestCase):

    def _test_sync(self, mock_call, return_value, cw_object, msg):
        mock_call(return_value)
        out = io.StringIO()
        call_command('cwsync', cw_object, stdout=out)
        self.assertIn(msg, out.getvalue().strip())


class TestSyncCompaniesCommand(BaseSyncTest):

    def test_sync(self):
        """Test sync companies command."""
        self._test_sync(
            mocks.company_api_get_call,
            fixtures.API_COMPANY_LIST,
            'company',
            sync_summary('Company')
        )


class TestSyncTeamsCommand(BaseSyncTest):

    def test_sync(self):
        """Test sync teams command."""
        fixture_utils.init_boards()
        self._test_sync(
            mocks.service_api_get_teams_call,
            [fixtures.API_SERVICE_TEAM_LIST[0]],
            'team',
            sync_summary('Team')
        )


class TestSyncBoardsCommand(BaseSyncTest):

    def test_sync(self):
        """Test sync boards command."""
        self._test_sync(
            mocks.service_api_get_boards_call,
            fixtures.API_BOARD_LIST,
            'board',
            sync_summary('Board')
        )


class TestSyncLocationsCommand(BaseSyncTest):

    def test_sync(self):
        """Test sync locations command."""
        self._test_sync(
            mocks.service_api_get_locations_call,
            fixtures.API_SERVICE_LOCATION_LIST,
            'location',
            sync_summary('Location')
        )


class TestSyncPrioritiesCommand(BaseSyncTest):

    def test_sync(self):
        """Test sync priorities command."""
        self._test_sync(
            mocks.service_api_get_priorities_call,
            fixtures.API_SERVICE_PRIORITY_LIST,
            'priority',
            sync_summary('Priority')
        )


class TestSyncProjectsCommand(BaseSyncTest):

    def test_sync(self):
        """Test sync projects command."""
        self._test_sync(
            mocks.project_api_get_projects_call,
            fixtures.API_PROJECT_LIST,
            'project',
            sync_summary('Project')
        )


class TestSyncBoardsStatusesCommand(BaseSyncTest):

    def setUp(self):
        board_synchronizer = sync.BoardSynchronizer()
        ConnectWiseBoard.objects.all().delete()
        _, _patch = mocks.service_api_get_boards_call(fixtures.API_BOARD_LIST)
        board_synchronizer.sync()
        _patch.stop()

    def test_sync(self):
        """Test sync_board_statuses command."""
        self._test_sync(
            mocks.service_api_get_statuses_call,
            fixtures.API_BOARD_STATUS_LIST,
            'board_status',
            sync_summary('Board Status')
        )


class TestSyncAllCommand(BaseSyncTest):
    def test_sync(self):
        """Test sync all objects command."""
        mocks.company_api_get_call(fixtures.API_COMPANY_LIST)
        mocks.service_api_get_boards_call(fixtures.API_BOARD_LIST)
        mocks.service_api_get_statuses_call(
            fixtures.API_BOARD_STATUS_LIST)
        mocks.system_api_get_members_call([fixtures.API_MEMBER])
        mocks.system_api_get_member_image_by_identifier_call(
            (mocks.CW_MEMBER_IMAGE_FILENAME, mocks.get_member_avatar()))
        mocks.company_api_by_id_call(fixtures.API_COMPANY)
        mocks.service_api_tickets_call()
        mocks.service_api_get_locations_call(
            fixtures.API_SERVICE_LOCATION_LIST)
        mocks.service_api_get_priorities_call(
            fixtures.API_SERVICE_PRIORITY_LIST)
        mocks.project_api_get_projects_call(
            fixtures.API_PROJECT_LIST)

        mocks.service_api_get_teams_call([fixtures.API_SERVICE_TEAM_LIST[0]])

        out = io.StringIO()
        call_command('cwsync', stdout=out)
        actual_output = out.getvalue().strip()

        summaries = [
            sync_summary('Priority'),
            sync_summary('Project'),
            sync_summary('Board'),
            sync_summary('Board Status'),
            sync_summary('Company'),
            sync_summary('Member'),
            sync_summary('Team'),
            sync_summary('Ticket')]

        for summary in summaries:
            self.assertIn(summary, actual_output)
