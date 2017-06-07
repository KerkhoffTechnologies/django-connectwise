from django.test import TestCase

from . import fixtures
from . import mocks

from djconnectwise import callback
from djconnectwise.models import CallBackEntry


class TestCallBackHandler(TestCase):
    handlers = [
        callback.TicketCallBackHandler,
        callback.ProjectCallBackHandler,
        callback.CompanyCallBackHandler,
        callback.OpportunityCallBackHandler
    ]

    def get_fixture(self):
        fixture = fixtures.API_SYSTEM_CALLBACK_ENTRY
        fixture['type'] = self.handler.CALLBACK_TYPE
        return fixture

    def clean(self):
        CallBackEntry.objects.all().delete()

    def _test_create_callback(self):
        self.clean()
        fixture = self.get_fixture()
        mocks.system_api_create_callback_call(fixture)
        entry = self.handler.create()

        self.assertEqual(entry.id, fixture['id'])
        self.assertEqual(entry.callback_type, fixture['type'])
        self.assertEqual(entry.url, fixture['url'])
        self.assertEqual(entry.level, fixture['level'])
        self.assertEqual(entry.description, fixture['description'])
        self.assertEqual(entry.object_id, fixture['objectId'])
        self.assertEqual(entry.member_id, fixture['memberId'])
        self.assertEqual(entry.inactive_flag, fixture['inactiveFlag'])

    def _test_delete_callback(self):
        self.clean()

        fixture = self.get_fixture()
        mocks.system_api_delete_callback_call({})
        mocks.system_api_create_callback_call(fixture)
        mocks.system_api_get_callbacks_call([fixture])
        entry = self.handler.create()
        callback_qset = CallBackEntry.objects.all()
        entries = list(callback_qset)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0], entry)

        self.handler.delete()
        self.assertEqual(entries[0], entry)
        self.assertEqual(CallBackEntry.objects.all().count(), 0)

    def test_create(self):
        for handler in self.handlers:
            self.handler = handler()
            self._test_create_callback()

    def test_delete(self):
        for handler in self.handlers:
            self.handler = handler()
            self._test_delete_callback()

    def test_get_callbacks(self):
        self.handler = self.handlers[0]()
        fixture = [fixtures.API_SYSTEM_CALLBACK_ENTRY]
        mocks.system_api_get_callbacks_call(fixture)

        callbacks = self.handler.get_callbacks()
        self.assertEqual(callbacks, fixture)
