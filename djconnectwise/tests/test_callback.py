from django.test import TestCase

from .. import api
from . import fixtures, fixture_utils
from . import mocks
from django.core.urlresolvers import reverse
from djconnectwise.callback import CallBackHandler


class TestCallBackHandler(TestCase):

    def setUp(self):
        self.client = api.ServiceAPIClient()
        self.handler = CallBackHandler()
        fixture_utils.init_members()

    def test_create_ticket_callback(self):
        reverse('djconnectwise:service-ticket-callback')
        fixture = fixtures.API_SYSTEM_CALLBACK_ENTRY
        mocks.system_api_create_callback_call(fixture)
        entry = self.handler.create_ticket_callback()

        self.assertEqual(entry.id, fixture['id'])
        self.assertEqual(entry.callback_type, fixture['type'])
        self.assertEqual(entry.url, fixture['url'])
        self.assertEqual(entry.level, fixture['level'])
        self.assertEqual(entry.description, fixture['description'])
        self.assertEqual(entry.object_id, fixture['objectId'])
        self.assertEqual(entry.member_id, fixture['memberId'])
        self.assertEqual(entry.inactive_flag, fixture['inactiveFlag'])

    def test_create_project_callback(self):
        reverse('djconnectwise:service-ticket-callback')
        fixture = fixtures.API_SYSTEM_CALLBACK_ENTRY
        mocks.system_api_create_callback_call(fixture)
        entry = self.handler.create_ticket_callback()

        self.assertEqual(entry.id, fixture['id'])
        self.assertEqual(entry.callback_type, fixture['type'])
        self.assertEqual(entry.url, fixture['url'])
        self.assertEqual(entry.level, fixture['level'])
        self.assertEqual(entry.description, fixture['description'])
        self.assertEqual(entry.object_id, fixture['objectId'])
        self.assertEqual(entry.member_id, fixture['memberId'])
        self.assertEqual(entry.inactive_flag, fixture['inactiveFlag'])

