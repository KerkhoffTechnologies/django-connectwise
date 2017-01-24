from django.test import TestCase

from ..api import (
    SystemAPIClient,
    ProjectAPIClient,
    ServiceAPIRestClient
)


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
        service_client = ServiceAPIRestClient()
        result = self.client.get_projects()
        boards_map = {}
        for r in result:
            boards_map[r['board']['id']] = r['board']

        print(boards_map)
        for board_id in list(boards_map.keys()):
            print(service_client.get_board(board_id))

        for b in service_client.get_boards():
            print(b['id'])

        self.assertIsNotNone(result)

