from django.test import TestCase

from ..api import CompanyAPIRestClient, ProjectAPIClient
from ..api import SystemAPIClient
from .mocks import company_api_get_call
from . import fixtures


class TestSystemAPIClient(TestCase):

    def setUp(self):
        self.client = SystemAPIClient()

    def test_get_connectwise_version(self):
        result = self.client.get_connectwise_version()
        self.assertIsNotNone(result)

    def test_get_members(self):
        result = self.client.get_members()
        self.assertIsNotNone(result)


class TestProjectAPIClient(TestCase):
    def setUp(self):
        self.client = ProjectAPIClient()

    def test_get_connectwise_version(self):
        result = self.client.get_projects()
        boards_map = {}
        for r in result:
            boards_map[r['board']['id']] = r['board']

        self.assertIsNotNone(result)


class TestCompanyAPIRestClient(TestCase):

    def setUp(self):
        super(TestCompanyAPIRestClient, self).setUp()
        self.client = CompanyAPIRestClient()

    def test_get(self):
        return_value = fixtures.API_COMPANY_LIST
        _, get_patch = company_api_get_call(return_value)

        result = self.client.get()
        get_patch.stop()

        self.assertEquals(len(result), len(return_value))

    def test_get_no_results(self):
        _, get_patch = company_api_get_call(None)

        result = self.client.get()
        get_patch.stop()

        self.assertIsNone(result)
