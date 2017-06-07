import responses


from django.conf import settings
from django.test import TestCase

from .. import api

from . import fixtures
from . import mocks as mk


API_URL = 'https://localhost/v4_6_release/apis/3.0/system/members/count'


class BaseAPITestCase(TestCase):

    def assertRequestShouldPage(self, should_page):
        request_url = responses.calls[0].request.url
        params = ['pageSize=1000', 'page=1']

        if should_page:
            for param in params:
                self.assertIn(param, request_url)
        else:
            for param in params:
                self.assertNotIn(param, request_url)


class TestServiceAPIClient(BaseAPITestCase):

    def setUp(self):
        self.client = api.ServiceAPIClient()

    def _get_boards_stub(self, return_value):
        endpoint = self.client._endpoint(self.client.ENDPOINT_BOARDS)
        return mk.get(endpoint, return_value)

    @responses.activate
    def test_get_boards(self):
        self._get_boards_stub(fixtures.API_BOARD_LIST)

        result = self.client.get_boards()
        self.assertEqual(result, fixtures.API_BOARD_LIST)
        self.assertRequestShouldPage(True)

    @responses.activate
    def test_get_boards_no_data(self):
        return_value = {}
        self._get_boards_stub(return_value)

        result = self.client.get_boards()
        self.assertEqual(result, return_value)

    @responses.activate
    def test_get_statuses(self):
        endpoint_url = 'boards/{}/statuses'.format(
            fixtures.API_BOARD['id'])

        endpoint_url = self.client._endpoint(endpoint_url)

        mk.get(endpoint_url, fixtures.API_BOARD_STATUS_LIST)

        result = self.client.get_statuses(fixtures.API_BOARD['id'])
        self.assertEqual(result, fixtures.API_BOARD_STATUS_LIST)
        self.assertRequestShouldPage(True)

    @responses.activate
    def test_get_priorities(self):
        endpoint_url = self.client._endpoint(self.client.ENDPOINT_PRIORITIES)
        mk.get(endpoint_url, fixtures.API_SERVICE_PRIORITY_LIST)

        result = self.client.get_priorities()
        self.assertEqual(result, fixtures.API_SERVICE_PRIORITY_LIST)
        self.assertRequestShouldPage(True)

    @responses.activate
    def test_get_teams(self):
        board_id = fixtures.API_BOARD_LIST[0]['id']
        endpoint = '{}/{}/teams/'.format(self.client.ENDPOINT_BOARDS, board_id)
        endpoint_url = self.client._endpoint(endpoint)
        mk.get(endpoint_url, fixtures.API_SERVICE_TEAM_LIST)
        result = self.client.get_teams(board_id)
        self.assertEqual(result, fixtures.API_SERVICE_TEAM_LIST)
        self.assertRequestShouldPage(True)

    @responses.activate
    def test_get_locations(self):
        endpoint_url = self.client._endpoint(self.client.ENDPOINT_LOCATIONS)
        mk.get(endpoint_url, fixtures.API_SERVICE_LOCATION_LIST)

        result = self.client.get_locations()
        self.assertEqual(result, fixtures.API_SERVICE_LOCATION_LIST)
        self.assertRequestShouldPage(True)


class TestSystemAPIClient(BaseAPITestCase):

    def setUp(self):
        self.client = api.SystemAPIClient()

    @responses.activate
    def test_get_connectwise_version(self):
        endpoint = self.client._endpoint(self.client.ENDPOINT_INFO)
        mk.get(endpoint,
               fixtures.API_CW_VERSION)
        result = self.client.get_connectwise_version()
        self.assertEqual(result, fixtures.API_CW_VERSION['version'])
        self.assertRequestShouldPage(False)

    @responses.activate
    def test_get_members(self):
        endpoint = self.client._endpoint(self.client.ENDPOINT_MEMBERS_COUNT)
        mk.get(endpoint,
               fixtures.API_MEMBER_COUNT)

        endpoint = self.client._endpoint(self.client.ENDPOINT_MEMBERS)
        mk.get(endpoint,
               fixtures.API_MEMBER_LIST)

        result = self.client.get_members()
        self.assertEqual(result, fixtures.API_MEMBER_LIST)
        self.assertRequestShouldPage(True)

    @responses.activate
    def test_get_member_image_by_identifier(self):
        member = fixtures.API_MEMBER
        # Requests will fake returning this as the filename
        avatar = mk.get_member_avatar()
        avatar_filename = 'AnonymousMember.png'
        endpoint = self.client._endpoint(
            self.client.ENDPOINT_MEMBERS_IMAGE.format(member['identifier']))
        mk.get_raw(
            endpoint,
            avatar,
            headers={
                'content-disposition':
                    'attachment; filename={}'.format(avatar_filename),
            }
        )

        result_filename, result_avatar = self.client \
            .get_member_image_by_identifier(member['identifier'])

        self.assertEqual(result_filename, avatar_filename)
        self.assertEqual(result_avatar, avatar)

    def test_attachment_filename_returns_filename(self):
        # It works with a file extension
        self.assertEqual(
            self.client._attachment_filename(
                'attachment; filename=somefile.jpg'
            ),
            'somefile.jpg',
        )
        # It also works without a file extension
        self.assertEqual(
            self.client._attachment_filename('attachment; filename=somefile'),
            'somefile',
        )
        # It also works with a space and quoted filename
        self.assertEqual(
            self.client._attachment_filename(
                'attachment; filename="somefile and a space.jpg"'
            ),
            'somefile and a space.jpg',
        )
        # And it works with Unicode
        filename = 'attachment; filename=Ƨōmefile.jpg'
        self.assertEqual(
            self.client._attachment_filename(filename),
            'Ƨōmefile.jpg',
        )

    def test_attachment_filename_returns_none_on_invalid(self):
        self.assertEqual(
            self.client._attachment_filename(''),
            None,
        )


class TestProjectAPIClient(BaseAPITestCase):
    def setUp(self):
        self.client = api.ProjectAPIClient()

    @responses.activate
    def test_get_projects(self):
        endpoint = self.client._endpoint(self.client.ENDPOINT_PROJECTS)
        mk.get(endpoint, fixtures.API_PROJECT_LIST)

        result = self.client.get_projects()

        self.assertIsNotNone(result)
        self.assertRequestShouldPage(True)


class TestCompanyAPIClient(BaseAPITestCase):

    def setUp(self):
        super(TestCompanyAPIClient, self).setUp()
        self.client = api.CompanyAPIClient()
        self.endpoint = self.client._endpoint(self.client.ENDPOINT_COMPANIES)

    @responses.activate
    def test_by_id(self):
        company_id = fixtures.API_COMPANY['id']
        endpoint_url = '{}/{}'.format(self.endpoint, company_id)

        mk.get(endpoint_url,
               fixtures.API_COMPANY)
        result = self.client.by_id(company_id)
        self.assertEqual(result, fixtures.API_COMPANY)
        self.assertRequestShouldPage(False)

    @responses.activate
    def test_get(self):
        mk.get(self.endpoint,
               fixtures.API_COMPANY_LIST)
        result = self.client.get_companies()
        self.assertEqual(len(result), len(fixtures.API_COMPANY_LIST))
        self.assertRequestShouldPage(True)

    @responses.activate
    def test_get_no_results(self):
        data = {}
        mk.get(self.endpoint,
               data)
        result = self.client.get_companies()

        self.assertEqual(result, data)

    @responses.activate
    def test_get_company_statuses(self):
        endpoint = self.client._endpoint(
            self.client.ENDPOINT_COMPANY_STATUSES)

        mk.get(endpoint, fixtures.API_COMPANY_STATUS_LIST)
        result = self.client.get_company_statuses()
        self.assertEqual(result, fixtures.API_COMPANY_STATUS_LIST)
        self.assertRequestShouldPage(True)


class TestSalesAPIClient(BaseAPITestCase):

    def setUp(self):
        super(TestSalesAPIClient, self).setUp()
        self.client = api.SalesAPIClient()
        self.endpoint = self.client._endpoint(
            self.client.ENDPOINT_OPPORTUNITY_STATUSES)

    @responses.activate
    def test_get_opportunities(self):
        endpoint = self.client._endpoint(
            self.client.ENDPOINT_OPPORTUNITIES)
        mk.get(endpoint, fixtures.API_SALES_OPPORTUNITIES)
        result = self.client.get_opportunities()
        self.assertEqual(result, fixtures.API_SALES_OPPORTUNITIES)
        self.assertRequestShouldPage(True)

    @responses.activate
    def test_get_opportunity_statuses(self):
        endpoint = self.client._endpoint(
            self.client.ENDPOINT_OPPORTUNITY_STATUSES)

        mk.get(endpoint, fixtures.API_SALES_OPPORTUNITY_STATUSES)
        result = self.client.get_opportunity_statuses()
        self.assertEqual(result, fixtures.API_SALES_OPPORTUNITY_STATUSES)
        self.assertRequestShouldPage(True)

    @responses.activate
    def test_get_opportunity_types(self):
        endpoint = self.client._endpoint(
            self.client.ENDPOINT_OPPORTUNITY_TYPES)

        mk.get(endpoint, fixtures.API_SALES_OPPORTUNITY_TYPES)
        result = self.client.get_opportunity_types()
        self.assertEqual(result, fixtures.API_SALES_OPPORTUNITY_TYPES)
        self.assertRequestShouldPage(True)


class TestAPISettings(TestCase):

    def test_default_timeout(self):
        client = api.ServiceAPIClient()
        self.assertEqual(client.timeout,
                         settings.DJCONNECTWISE_API_TIMEOUT)

    def test_dynamic_batch_size(self):
        method_name = 'djconnectwise.utils.RequestSettings.get_settings'
        request_settings = {
            'batch_size': 10,
            'timeout': 10,
        }
        _, _patch = mk.create_mock_call(method_name, request_settings)
        client = api.ServiceAPIClient()

        self.assertEqual(client.timeout,
                         request_settings['timeout'])
        _patch.stop()
