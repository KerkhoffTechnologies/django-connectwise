import json
import copy
from . import fixtures, fixture_utils, mocks

from django.core.urlresolvers import reverse
from django.test import Client, TestCase

from djconnectwise.models import CallBackEntry, Company, Ticket, Project
from djconnectwise import views, api


class BaseTestCallBackView(TestCase):
    MODEL_CLASS = None

    def setUp(self):
        fixture_utils.init_boards()
        fixture_utils.init_board_statuses()
        fixture_utils.init_members()

    def assert_fields(self, instance, entity):
        raise NotImplementedError

    def post_data(self, callback_type, action, entity_id, entity=None):
        client = Client()
        body = {
            'Type': callback_type,
            'Action': action,
            'ID': entity_id,
            'Entity': json.dumps(entity) if entity else None,
        }
        body_json = json.dumps(body)

        return client.post(
            reverse('djconnectwise:callback'),
            body_json,
            content_type="application/json"
        )

    def _test_added(self, callback_type, entity):
        response = self.post_data(
            callback_type,
            views.CALLBACK_ADDED,
            entity['id'],
            entity
        )

        instances = list(self.MODEL_CLASS.objects.all())
        instance = instances[0]

        self.assert_fields(instance, entity)
        self.assertEqual(instance.id, entity['id'])
        self.assertEqual(len(instances), 1)
        self.assertEqual(response.status_code, 204)

    def _test_update(self, callback_type, entity):
        response = self.post_data(
            callback_type,
            views.CALLBACK_UPDATED,
            entity['id'],
            entity
        )

        instances = list(self.MODEL_CLASS.objects.all())
        instance = instances[0]

        self.assert_fields(instance, entity)
        self.assertEqual(instance.id, entity['id'])
        self.assertEqual(len(instances), 1)
        self.assertEqual(response.status_code, 204)

    def _test_delete(self, callback_type, entity_id):
        response = self.post_data(
            callback_type,
            views.CALLBACK_DELETED,
            entity_id
        )
        instances = list(self.MODEL_CLASS.objects.all())
        self.assertEqual(response.status_code, 204)
        self.assertEqual(len(instances), 0)


class TestTicketCallBackView(BaseTestCallBackView):
    MODEL_CLASS = Ticket

    def assert_fields(self, instance, entity):
        self.assertEqual(instance.summary, entity['summary'])

    def test_add(self):
        self.assertEqual(Ticket.objects.count(), 0)
        mocks.service_api_get_ticket_call()
        self._test_added(CallBackEntry.TICKET, fixtures.API_SERVICE_TICKET)

    def test_update(self):
        fixture_utils.init_tickets()
        self.assertEqual(Ticket.objects.count(), 1)
        # Change the summary of the local record to make our test meaningful.
        t = Ticket.objects.get(id=69)
        t.summary = 'foobar'
        t.save()

        mocks.service_api_get_ticket_call()
        self._test_update(CallBackEntry.TICKET, fixtures.API_SERVICE_TICKET)

    def test_delete(self):
        fixture_utils.init_tickets()
        self.assertEqual(Ticket.objects.count(), 1)

        mocks.service_api_get_ticket_call(api.ConnectWiseRecordNotFoundError)
        self._test_delete(
            CallBackEntry.TICKET,
            fixtures.API_SERVICE_TICKET['id']
        )


class TestProjectCallBackView(BaseTestCallBackView):
    MODEL_CLASS = Project

    def assert_fields(self, instance, entity):
        self.assertEqual(instance.name, entity['name'])

    def test_add(self):
        self.assertEqual(Project.objects.count(), 0)
        mocks.project_api_get_project_call(fixtures.API_PROJECT)
        self._test_added(CallBackEntry.PROJECT, fixtures.API_PROJECT)

    def test_update(self):
        fixture_utils.init_projects()
        self.assertEqual(Project.objects.count(), 1)
        # Change the name of the local record to make our test meaningful.
        p = Project.objects.get(id=5)
        p.name = 'foobar'
        p.save()

        mocks.project_api_get_project_call(fixtures.API_PROJECT)
        self._test_update(CallBackEntry.PROJECT, fixtures.API_PROJECT)

    def test_delete(self):
        fixture_utils.init_projects()
        self.assertEqual(Project.objects.count(), 1)

        mocks.project_api_get_project_call(
            None,
            raised=api.ConnectWiseRecordNotFoundError
        )
        self._test_delete(
            CallBackEntry.PROJECT,
            fixtures.API_PROJECT['id']
        )


class TestCompanyCallBackView(BaseTestCallBackView):
    MODEL_CLASS = Company

    def assert_fields(self, instance, entity):
        self.assertEqual(instance.name, entity['name'])

    def test_add(self):
        self.assertEqual(Company.objects.count(), 0)
        mocks.company_api_by_id_call(fixtures.API_COMPANY)
        self._test_added(CallBackEntry.COMPANY, fixtures.API_COMPANY)

    def test_update(self):
        fixture_utils.init_companies()
        self.assertEqual(Company.objects.count(), 1)
        # Change the name of the local record to make our test meaningful.
        c = Company.objects.get(id=2)
        c.name = 'foobar'
        c.save()

        mocks.company_api_by_id_call(fixtures.API_COMPANY)
        self._test_update(CallBackEntry.COMPANY, fixtures.API_COMPANY)

    def test_delete(self):
        fixture_utils.init_companies()
        self.assertEqual(Company.objects.count(), 1)

        # In CW, companies are not deleted- only their deletedFlag field is
        # set.
        company_fixture = copy.deepcopy(fixtures.API_COMPANY)
        company_fixture['deletedFlag'] = True
        mocks.company_api_by_id_call(company_fixture)
        self._test_delete(
            CallBackEntry.COMPANY,
            company_fixture['id']
        )
