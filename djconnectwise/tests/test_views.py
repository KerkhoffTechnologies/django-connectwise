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

    def _test_update(self, callback_type, entity):
        client = Client()
        fixture = self.get_fixture()
        fixture['Entity'] = json.dumps(entity)
        fixture['Type'] = callback_type

        json_data = json.dumps(fixture)

        response = client.post(reverse('djconnectwise:ticket-callback'),
                               json_data,
                               content_type="application/json")

        instances = list(self.MODEL_CLASS.objects.all())
        instance = instances[0]

        self.assertEqual(response.status_code, 204)
        self.assertEqual(len(instances), 1)
        self.assertEqual(instance.id, entity['id'])
        self.assert_fields(instance, entity)


class TestTicketCallBackView(BaseTestCallBackView):
    MODEL_CLASS = Ticket

    def test_update(self):
        fixture = self.get_fixture()
        entity = json.loads(fixture['Entity'])
        self._test_update(CallBackEntry.TICKET, entity)

    def assert_fields(self, instance, entity):
        self.assertEqual(instance.summary, entity['summary'])


class TestProjectCallBackView(BaseTestCallBackView):
    MODEL_CLASS = Project

    def assert_fields(self, instance, entity):
        self.assertEqual(instance.name, entity['name'])

    def test_update(self):
        entity = fixtures.API_PROJECT
        self._test_update(CallBackEntry.PROJECT, entity)


class TestCompanyCallBackView(BaseTestCallBackView):
    MODEL_CLASS = Company

    def assert_fields(self, instance, entity):
        self.assertEqual(instance.name, entity['name'])

    def test_update(self):
        entity = fixtures.API_COMPANY
        self._test_update(CallBackEntry.COMPANY, entity)
