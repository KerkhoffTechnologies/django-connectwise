from django.test import TestCase

from ..api import SystemAPIClient, ProjectAPIClient


class TestSystemAPIClient(TestCase):

    def setUp(self):
        self.client = SystemAPIClient()

    def test_get_connectwise_version(self):
        result = self.client.get_connectwise_version()
        self.assertIsNotNone(result)

    def test_get_members(self):
        result = self.client.get_members()
        print(result)
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
