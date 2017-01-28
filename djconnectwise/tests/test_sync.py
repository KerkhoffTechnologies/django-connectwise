import random
import time

from djconnectwise.models import ServiceTicket, TicketStatus
from test_plus.test import TestCase

from ..sync import ServiceTicketSynchronizer


# TODO: setup no longer applies since it is used in the
# core application

# setup.SETUP_DATA_FILE_NAME = 'data/test_setup.json'


class TestServiceTicketSynchronizer(TestCase):

    def setUp(self):
        # setup.init()
        self.synchronizer = ServiceTicketSynchronizer()
        self.synchronizer.sync_tickets()

    def _get_local_and_api_ticket(self):
        api_ticket = self.synchronizer.service_client.get_tickets(
            page=random.randrange(1, 100, 2), page_size=1)[0]
        local_ticket, created = self.synchronizer.sync_ticket(api_ticket)
        return local_ticket, api_ticket

    def test_sync_tickets(self):
        num_tickets = self.synchronizer.service_client.tickets_count()

        start = time.time()
        created_count, updated_count, delete_count = self.synchronizer \
                                                         .sync_tickets()
        end = time.time()

        # sync took less than 60 seconds
        self.assertLess(end - start, 45)

        self.assertEqual(num_tickets, ServiceTicket.objects.all().count())

    def test_update_api_ticket(self):
        local_ticket, api_ticket = self._get_local_and_api_ticket()
        # find a new random status
        ticket_status_types = [s for s in TicketStatus.objects.all()]
        status_index = random.randrange(0, len(ticket_status_types), 1)

        local_ticket.status = ticket_status_types[status_index]
        local_ticket.save()
        self.synchronizer.update_api_ticket(local_ticket)
        updated_api_ticket = self.synchronizer.service_client.get_ticket(
            local_ticket.id)
        self.assertEqual(updated_api_ticket['status'][
                         'name'], local_ticket.status.status_name)

    def test_close_ticket(self):
        local_ticket, api_ticket = self._get_local_and_api_ticket()
        self.synchronizer.close_ticket(local_ticket)

        updated_api_ticket = self.synchronizer.service_client.get_ticket(
            local_ticket.id)
        self.assertTrue(updated_api_ticket['closedFlag'])


class TestMemberSynchronization(TestCase):

    def setUp(self):
        # setup.init()
        self.synchronizer = ServiceTicketSynchronizer()

    def test_sync_member(self):

        # get members list
        local_members = [m for m in list(self.synchronizer.members_map.keys())]
        members_json = self.synchronizer.system_client.get_members()
        api_members = []

        for member in members_json:
            if member['identifier'] not in local_members:
                api_members.append(member)

        if api_members:

            new_member = self.synchronizer.sync_member(
                api_members[0]['identifier'])
            user = new_member.user
            original_name = new_member.user.name
            user.name = 'some name'
            user.save()

            new_member = self.synchronizer.sync_member(
                api_members[0]['identifier'])

            # verify that the fields are syncing as expected
            self.assertEqual(new_member.user.name, original_name)

        else:
            raise ValueError('No members to test')
