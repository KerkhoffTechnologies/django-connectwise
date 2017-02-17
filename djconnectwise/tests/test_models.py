from django.test import TestCase
from djconnectwise.models import ServiceTicket


class TestServiceTicket(TestCase):

    def test_str(self):
        t = ServiceTicket(id=1, summary='Únicôde wôrks!')
        self.assertEqual(
            '{}'.format(t),
            '1-Únicôde wôrks!'
        )
