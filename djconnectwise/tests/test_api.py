import responses
import requests
from urllib.parse import urljoin
# import json

from django.core.cache import cache
from django.test import TestCase

from .. import api

from . import fixtures
from . import mocks as mk

from djconnectwise.api import ConnectWiseAPIError, ConnectWiseAPIClientError
from djconnectwise.api import ConnectWiseRecordNotFoundError
from djconnectwise.api import CompanyInfoManager


API_URL = 'https://localhost/v4_6_release/apis/3.0/system/members/count'


class BaseAPITestCase(TestCase):

    def assert_request_should_page(self, should_page):
        request_url = responses.calls[0].request.url
        params = ['pageSize=1000', 'page=1']

        if should_page:
            for param in params:
                self.assertIn(param, request_url)
        else:
            for param in params:
                self.assertNotIn(param, request_url)


class TestConnectWiseAPIClient(TestCase):
    def setUp(self):
        self.client = api.ServiceAPIClient()  # Must use a real client as
        # ConnectWiseAPIClient is effectively abstract

    def test_prepare_conditions_single(self):
        conditions = [
            'closedFlag = False',
        ]
        self.assertEqual(
            self.client.prepare_conditions(conditions),
            '(closedFlag = False)'
        )

    def test_prepare_conditions_multiple(self):
        conditions = [
            'closedFlag = False',
            'status/id in (1,2,3)',
        ]
        self.assertEqual(
            self.client.prepare_conditions(conditions),
            '(closedFlag = False and status/id in (1,2,3))'
        )

    @responses.activate
    def test_request(self):
        endpoint = 'http://example.com/'
        response = 'ok'
        responses.add(responses.GET, endpoint, json=response, status=200)

        result = self.client.request('get', endpoint, None)
        self.assertEqual(result, response)

    @responses.activate
    def test_request_failure(self):
        endpoint = 'http://example.com/'
        responses.add(
            responses.GET, endpoint, body=requests.RequestException()
        )

        with self.assertRaises(ConnectWiseAPIError):
            self.client.request('get', endpoint, None)

    @responses.activate
    def test_request_400(self):
        endpoint = 'http://example.com/'
        response = {'error': 'this is bad'}
        responses.add(responses.GET, endpoint, json=response, status=400)

        with self.assertRaises(ConnectWiseAPIError):
            self.client.request('get', endpoint, None)


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
        self.assert_request_should_page(True)

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
        self.assert_request_should_page(True)

    @responses.activate
    def test_get_priorities(self):
        endpoint_url = self.client._endpoint(self.client.ENDPOINT_PRIORITIES)
        mk.get(endpoint_url, fixtures.API_SERVICE_PRIORITY_LIST)

        result = self.client.get_priorities()
        self.assertEqual(result, fixtures.API_SERVICE_PRIORITY_LIST)
        self.assert_request_should_page(True)

    @responses.activate
    def test_get_teams(self):
        board_id = fixtures.API_BOARD_LIST[0]['id']
        endpoint = '{}/{}/teams/'.format(self.client.ENDPOINT_BOARDS, board_id)
        endpoint_url = self.client._endpoint(endpoint)
        mk.get(endpoint_url, fixtures.API_SERVICE_TEAM_LIST)
        result = self.client.get_teams(board_id)
        self.assertEqual(result, fixtures.API_SERVICE_TEAM_LIST)
        self.assert_request_should_page(True)

    @responses.activate
    def test_get_locations(self):
        endpoint_url = self.client._endpoint(self.client.ENDPOINT_LOCATIONS)
        mk.get(endpoint_url, fixtures.API_SERVICE_LOCATION_LIST)

        result = self.client.get_locations()
        self.assertEqual(result, fixtures.API_SERVICE_LOCATION_LIST)
        self.assert_request_should_page(True)


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
        self.assert_request_should_page(False)

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
        self.assert_request_should_page(True)

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
        self.assert_request_should_page(True)


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
        self.assert_request_should_page(False)

    @responses.activate
    def test_get(self):
        mk.get(self.endpoint,
               fixtures.API_COMPANY_LIST)
        result = self.client.get_companies()
        self.assertEqual(len(result), len(fixtures.API_COMPANY_LIST))
        self.assert_request_should_page(True)

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
        self.assert_request_should_page(True)


class TestScheduleAPIClient(BaseAPITestCase):

    def setUp(self):
        super(TestScheduleAPIClient, self).setUp()
        self.client = api.ScheduleAPIClient()
        self.endpoint = self.client._endpoint(self.client.ENDPOINT_ENTRIES)

    @responses.activate
    def test_get_schedule_types(self):
        endpoint = self.client._endpoint(self.client.ENDPPOINT_SCHEDULE_TYPES)

        mk.get(endpoint, fixtures.API_SCHEDULE_TYPE_LIST)
        result = self.client.get_schedule_types()
        self.assertEqual(result, fixtures.API_SCHEDULE_TYPE_LIST)
        self.assert_request_should_page(True)

    @responses.activate
    def test_get_schedule_statuses(self):
        endpoint = self.client._endpoint(self.client.ENDPOINT_SCHEDULE_STATUSES)

        mk.get(endpoint, fixtures.API_SCHEDULE_STATUS_LIST)
        result = self.client.get_schedule_statuses()
        self.assertEqual(result, fixtures.API_SCHEDULE_STATUS_LIST)
        self.assert_request_should_page(True)

    @responses.activate
    def test_get_schedule_entries(self):
        endpoint = self.client._endpoint(self.client.ENDPOINT_ENTRIES)

        mk.get(endpoint, fixtures.API_SCHEDULE_ENTRIES)
        result = self.client.get_schedule_entries()
        self.assertEqual(result, fixtures.API_SCHEDULE_ENTRIES)
        self.assert_request_should_page(True)

    @responses.activate
    def test_get_schedule_entry(self):
        entry_id = fixtures.API_SCHEDULE_ENTRY['id']
        endpoint_url = '{}/{}'.format(self.endpoint, entry_id)

        mk.get(endpoint_url, fixtures.API_SCHEDULE_ENTRY)
        result = self.client.get_schedule_entry(entry_id)
        self.assertEqual(result, fixtures.API_SCHEDULE_ENTRY)
        self.assert_request_should_page(False)


class TestFetchAPICodebase(TestCase):
    HOST = 'https://na.myconnectwise.net'

    def setUp(self):
        self.manager = CompanyInfoManager()

    def _some_end_point(self):
        return urljoin(self.HOST, 'some-endpoint')

    def test_fetch_api_codebase_bad_url(self):
        api_codebase, updated = self.manager.fetch_api_codebase('')
        self.assertEqual(api_codebase,
                         api.DEFAULT_CW_API_CODEBASE)

    @responses.activate
    def test_fetch_api_company_info_endpoint_unavailable(self):
        mk.get(urljoin(self.HOST, api.CompanyInfoManager.COMPANYINFO_PATH),
               fixtures.API_COMPANY_INFO,
               status=503)
        cache.clear()
        with self.assertRaises(ConnectWiseAPIError):
            endpoint = self._some_end_point()
            api_codebase, updated = self.manager.fetch_api_codebase(endpoint)

    @responses.activate
    def test_fetch_api_codebase_added_to_cache(self):
        cache.clear()
        mk.get(urljoin(self.HOST, api.CompanyInfoManager.COMPANYINFO_PATH),
               fixtures.API_COMPANY_INFO)

        api_codebase, updated = self.manager.fetch_api_codebase(
            self.HOST,
        )

        self.assertEqual(api_codebase, fixtures.API_COMPANY_INFO['Codebase'])
        self.assertEqual(api_codebase, cache.get('api_codebase'))

    def test_fetch_api_codebase_from_warm_cache(self):
        cache.set('api_codebase',
                  fixtures.API_COMPANY_INFO['Codebase'])
        mock_get_call, _patch = \
            mk.company_info_get_company_info_call(fixtures.API_COMPANY_INFO)
        api_codebase, updated = self.manager.fetch_api_codebase(
            self._some_end_point())
        self.assertEqual(api_codebase, cache.get('api_codebase'))
        _patch.stop()


class TestSalesAPIClient(BaseAPITestCase):

    def setUp(self):
        super(TestSalesAPIClient, self).setUp()
        self.client = api.SalesAPIClient()
        self.endpoint = self.client._endpoint(
            self.client.ENDPOINT_OPPORTUNITY_STATUSES)

    @responses.activate
    def test_by_id(self):
        endpoint = self.client._endpoint(
            self.client.ENDPOINT_OPPORTUNITIES)
        json_data = fixtures.API_SALES_OPPORTUNITIES[0]
        instance_id = json_data['id']
        endpoint = '{}/{}'.format(endpoint, instance_id)
        mk.get(endpoint, json_data)
        result = self.client.by_id(instance_id)
        self.assertEqual(result, json_data)

    @responses.activate
    def test_get_opportunities(self):
        endpoint = self.client._endpoint(
            self.client.ENDPOINT_OPPORTUNITIES)
        mk.get(endpoint, fixtures.API_SALES_OPPORTUNITIES)
        result = self.client.get_opportunities()
        self.assertEqual(result, fixtures.API_SALES_OPPORTUNITIES)
        self.assert_request_should_page(True)

    @responses.activate
    def test_get_opportunity_statuses(self):
        endpoint = self.client._endpoint(
            self.client.ENDPOINT_OPPORTUNITY_STATUSES)

        mk.get(endpoint, fixtures.API_SALES_OPPORTUNITY_STATUSES)
        result = self.client.get_opportunity_statuses()
        self.assertEqual(result, fixtures.API_SALES_OPPORTUNITY_STATUSES)
        self.assert_request_should_page(True)

    @responses.activate
    def test_get_opportunity_types(self):
        endpoint = self.client._endpoint(
            self.client.ENDPOINT_OPPORTUNITY_TYPES)

        mk.get(endpoint, fixtures.API_SALES_OPPORTUNITY_TYPES)
        result = self.client.get_opportunity_types()
        self.assertEqual(result, fixtures.API_SALES_OPPORTUNITY_TYPES)
        self.assert_request_should_page(True)


class TestAPISettings(TestCase):

    def get_cloud_client(self):
        server_url = 'https://{}'.format(api.CW_CLOUD_DOMAIN)
        return api.ServiceAPIClient(server_url=server_url)

    def test_default_timeout(self):
        client = api.ServiceAPIClient()
        self.assertEqual(client.timeout, 30.0)

    def test_dynamic_batch_size(self):
        method_name = 'djconnectwise.utils.RequestSettings.get_settings'
        request_settings = {
            'batch_size': 10,
            'timeout': 10.0,
        }
        _, _patch = mk.create_mock_call(method_name, request_settings)
        client = api.ServiceAPIClient()

        self.assertEqual(client.timeout,
                         request_settings['timeout'])
        _patch.stop()

    def test_retry_attempts(self):
        with self.assertRaises(ConnectWiseAPIError):
            retry_counter = {'count': 0}
            client = api.ServiceAPIClient()
            client.fetch_resource('localhost/some-bad-url',
                                  retry_counter=retry_counter)
            self.assertEqual(retry_counter['count'],
                             client.request_settings['max_attempts'])

    @responses.activate
    def test_no_retry_attempts_in_400_range(self):
        client = api.ServiceAPIClient()
        endpoint = client._endpoint(
            api.ServiceAPIClient.ENDPOINT_TICKETS)

        tested_status_codes = []
        http_400_range = list(range(400, 499))
        # remove 404 code
        http_400_range.pop(4)

        for status_code in http_400_range:

            retry_counter = {'count': 0}
            try:
                mk.get(endpoint, {}, status=status_code)
                client.fetch_resource(
                    api.ServiceAPIClient.ENDPOINT_TICKETS,
                    retry_counter=retry_counter)
            except ConnectWiseAPIClientError:
                self.assertEqual(retry_counter['count'], 1)
                tested_status_codes.append(status_code)

        self.assertEqual(tested_status_codes, http_400_range)

    @responses.activate
    def test_no_retry_attempts_404_default_code_base(self):
        """
        Request should not be retried if a 404 is thrown, when
        request contains default codebase in url
        """
        client = api.ServiceAPIClient()
        mock_get_call, _patch = \
            mk.company_info_get_company_info_call(fixtures.API_COMPANY_INFO)
        endpoint = client._endpoint(
            api.ServiceAPIClient.ENDPOINT_TICKETS)

        retry_counter = {'count': 0}
        mk.get(endpoint, {}, status=404)

        with self.assertRaises(ConnectWiseRecordNotFoundError):
            client.fetch_resource(
                api.ServiceAPIClient.ENDPOINT_TICKETS,
                retry_counter=retry_counter)

        self.assertEqual(retry_counter['count'], 1)
        _patch.stop()

    @responses.activate
    def test_retry_attempts_cloud_domain_cold_cache(self):
        """
        Request should be retried if a 404 is thrown, when
        request contains the cw domain and the CodeBase value
        is not found in the cache
        """
        mock_get_call, _patch = \
            mk.company_info_get_company_info_call(fixtures.API_COMPANY_INFO)
        client = self.get_cloud_client()

        endpoint = client._endpoint(
            api.ServiceAPIClient.ENDPOINT_TICKETS)

        retry_counter = {'count': 0}
        mk.get(endpoint, {}, status=404)
        _patch.stop()

        with self.assertRaises(ConnectWiseRecordNotFoundError):
            client.fetch_resource(
                api.ServiceAPIClient.ENDPOINT_TICKETS,
                retry_counter=retry_counter)
        self.assertEqual(
            retry_counter['count'],
            api.ServiceAPIClient.MAX_404_ATTEMPTS + 1
        )

    @responses.activate
    def test_retry_attempts_cloud_domain_warm_cache(self):
        """
        Request should be retried if a 404 is thrown, when
        request contains the cw domain and the Codebase value
        is found in the cache.
        """
        cache.set('api_codebase', fixtures.API_COMPANY_INFO['Codebase'])
        client = self.get_cloud_client()
        endpoint = client._endpoint(api.ServiceAPIClient.ENDPOINT_TICKETS)

        retry_counter = {'count': 0}
        mk.get(endpoint, {}, status=404)

        with self.assertRaises(ConnectWiseRecordNotFoundError):
            client.fetch_resource(
                api.ServiceAPIClient.ENDPOINT_TICKETS,
                retry_counter=retry_counter
            )
        self.assertEqual(
            retry_counter['count'],
            api.ServiceAPIClient.MAX_404_ATTEMPTS + 1
        )
