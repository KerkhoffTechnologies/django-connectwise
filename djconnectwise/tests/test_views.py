from copy import deepcopy
import json

from . import fixtures, fixture_utils

from django.core.urlresolvers import reverse
from django.test import Client, TestCase

from djconnectwise.models import CallBackEntry, Company, Ticket, Project


class BaseTestCallBackView(TestCase):
    MODEL_CLASS = None

    def setUp(self):
        self.clean()
        fixture_utils.init_boards()
        fixture_utils.init_board_statuses()
        fixture_utils.init_members()

    def clean(self):
        self.MODEL_CLASS.objects.all().delete()

    def get_fixture(self):
        return deepcopy(fixtures.TICKET_CALLBACK_JSON_BODY)

    def assert_fields(self, instance, entity):
        raise NotImplementedError

    def post_data(self, callback_type, entity, action=None):
        client = Client()
        fixture = self.get_fixture()
        fixture['Entity'] = json.dumps(entity)
        fixture['Type'] = callback_type

        if action:
            fixture['Action'] = action

        json_data = json.dumps(fixture)

        return client.post(reverse('djconnectwise:callback'),
                           json_data,
                           content_type="application/json")

    def _test_update(self, callback_type, entity):
        response = self.post_data(callback_type, entity)

        instances = list(self.MODEL_CLASS.objects.all())
        instance = instances[0]

        self.assertEqual(response.status_code, 204)
        self.assertEqual(len(instances), 1)
        self.assertEqual(instance.id, entity['id'])
        self.assert_fields(instance, entity)

    def _test_delete(self, callback_type, entity):
        self.clean()
        # generate the ticket
        self._test_update(callback_type, entity)

        response = self.post_data(callback_type, entity, action='deleted')
        instances = list(self.MODEL_CLASS.objects.all())
        self.assertEqual(response.status_code, 204)
        self.assertEqual(len(instances), 0)


class TestTicketCallBackView(BaseTestCallBackView):
    MODEL_CLASS = Ticket

    def get_entity(self):
        fixture = self.get_fixture()
        return json.loads(fixture['Entity'])

    def test_update(self):
        self._test_update(CallBackEntry.TICKET, self.get_entity())

    def test_delete(self):
        self._test_delete(CallBackEntry.TICKET, self.get_entity())

    def assert_fields(self, instance, entity):
        self.assertEqual(instance.summary, entity['summary'])


class TestProjectCallBackView(BaseTestCallBackView):
    MODEL_CLASS = Project

    def assert_fields(self, instance, entity):
        self.assertEqual(instance.name, entity['name'])

    def test_update(self):
        self._test_update(CallBackEntry.PROJECT, fixtures.API_PROJECT)

    def test_delete(self):
        self._test_delete(CallBackEntry.PROJECT, fixtures.API_PROJECT)


class TestCompanyCallBackView(BaseTestCallBackView):
    MODEL_CLASS = Company

    def assert_fields(self, instance, entity):
        self.assertEqual(instance.name, entity['name'])

    def test_update(self):
        self._test_update(CallBackEntry.COMPANY, fixtures.API_COMPANY)

    def test_delete(self):
        self._test_delete(CallBackEntry.COMPANY, fixtures.API_COMPANY)
