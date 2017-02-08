import responses

from django.test import TestCase

from .. import api

from . import fixtures
from . import mocks as mk


API_URL = 'https://localhost/v4_6_release/apis/3.0/system/members/count'


class TestServiceAPIClient(TestCase):

    def setUp(self):
        self.client = api.ServiceAPIClient()

    def _get_boards_stub(self, return_value):
        endpoint = self.client._endpoint(self.client.ENDPOINT_BOARDS)
        return mk.get(endpoint, return_value)

    @responses.activate
    def test_get_boards(self):
        self._get_boards_stub(fixtures.API_BOARD_LIST)

        result = self.client.get_boards()
        self.assertEquals(result, fixtures.API_BOARD_LIST)

    @responses.activate
    def test_get_boards_no_data(self):
        return_value = {}
        self._get_boards_stub(return_value)

        result = self.client.get_boards()
        self.assertEquals(result, return_value)


class TestSystemAPIClient(TestCase):

    def setUp(self):
        self.client = api.SystemAPIClient()

    @responses.activate
    def test_get_connectwise_version(self):
        endpoint = self.client._endpoint(self.client.ENDPOINT_INFO)
        mk.get(endpoint,
               fixtures.API_CW_VERSION)
        result = self.client.get_connectwise_version()
        self.assertEquals(result, fixtures.API_CW_VERSION['version'])

    @responses.activate
    def test_get_members(self):
        endpoint = self.client._endpoint(self.client.ENDPOINT_MEMBERS_COUNT)
        mk.get(endpoint,
               fixtures.API_MEMBER_COUNT)

        endpoint = self.client._endpoint(self.client.ENDPOINT_MEMBERS)
        mk.get(endpoint,
               fixtures.API_MEMBER_LIST)

        result = self.client.get_members()
        self.assertEquals(result, fixtures.API_MEMBER_LIST)


class TestProjectAPIClient(TestCase):
    def setUp(self):
        self.client = api.ProjectAPIClient()

    @responses.activate
    def test_get_projects(self):
        endpoint = self.client._endpoint(self.client.ENDPOINT_PROJECT)
        mk.get(endpoint,
               fixtures.API_PROJECTS)

        result = self.client.get_projects()

        self.assertIsNotNone(result)


class TestCompanyAPIClient(TestCase):

    def setUp(self):
        super(TestCompanyAPIClient, self).setUp()
        self.client = api.CompanyAPIClient()
        self.endpoint = self.client._endpoint(self.client.ENDPOINT_COMPANIES)

    @responses.activate
    def test_get(self):
        mk.get(self.endpoint,
               fixtures.API_COMPANY_LIST)
        result = self.client.get()
        self.assertEquals(len(result), len(fixtures.API_COMPANY_LIST))

    @responses.activate
    def test_get_no_results(self):
        data = {}
        mk.get(self.endpoint,
               data)
        result = self.client.get()
        self.assertEquals(result, data)
