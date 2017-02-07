import responses

from django.test import TestCase

from ..api import CompanyAPIRestClient, ProjectAPIClient
from ..api import SystemAPIClient

from . import fixtures
from . import mocks as mk


API_URL = 'https://localhost/v4_6_release/apis/3.0/system/members/count'


class TestSystemAPIClient(TestCase):

    def setUp(self):
        self.client = SystemAPIClient()

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
        self.client = ProjectAPIClient()

    @responses.activate
    def test_get_projects(self):
        endpoint = self.client._endpoint(self.client.ENDPOINT_PROJECT)
        mk.get(endpoint,
               fixtures.API_PROJECTS)

        result = self.client.get_projects()

        self.assertIsNotNone(result)


class TestCompanyAPIRestClient(TestCase):

    def setUp(self):
        super(TestCompanyAPIRestClient, self).setUp()
        self.client = CompanyAPIRestClient()
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
