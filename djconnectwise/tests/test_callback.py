import responses

from django.test import TestCase

from .. import api

from . import fixtures
from . import mocks as mk
from django.core.urlresolvers import reverse
from djconnectwise.callback import CallBackHandler


class TestCallBackHandler(TestCase):

    def setUp(self):
        self.client = api.ServiceAPIClient()
        self.handler = CallBackHandler()

    def test_create_ticket_callback(self):
        reverse('djconnectwise:service-ticket-callback')
        #self.handler.create_ticket_callback()
