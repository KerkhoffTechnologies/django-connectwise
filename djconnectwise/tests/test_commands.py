import io

from django.core.management import call_command
from django.test import TestCase

from .mocks import company_api_get_call
from . import fixtures


class TestSyncCompaniesCommand(TestCase):

    def test_sync_companies(self):
        " Test sync companies command."
        _, get_patch = company_api_get_call(fixtures.API_COMPANY_LIST)
        out = io.StringIO()
        call_command('sync_companies', stdout=out)
        msg = 'Synced Companies - Created: 1 , Updated: 0'
        self.assertIn(msg, out.getvalue().strip())
