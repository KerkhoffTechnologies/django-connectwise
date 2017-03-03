from django.test import TestCase
from djconnectwise.models import Ticket, TicketPriority


class TestTicketPriority(TestCase):

    def test_priority_color(self):
        # If a priority has a color, then the property returns it.
        p = TicketPriority(name='Priority 1 - Emergency Response')
        # This also tests the setter.
        p.color = 'PapayaWhip'  # Yeah, PapayaWhip is a CSS color
        self.assertEqual(p.color, 'PapayaWhip')

    def test_priority_color_property(self):
        # If a priority doesn't have a color, then the property returns
        # a sensible default.
        p = TicketPriority(name='Priority 1 - Emergency Response')
        self.assertEqual(p.color, 'red')
        p = TicketPriority(name='Priority 2 - Quick Response')
        self.assertEqual(p.color, 'orange')
        p = TicketPriority(name='Priority 3 - Normal Response')
        self.assertEqual(p.color, 'yellow')
        p = TicketPriority(name='Priority 4 - Scheduled Maintenance')
        self.assertEqual(p.color, 'white')
        p = TicketPriority(name='Priority 5 - Next Time')
        self.assertEqual(p.color, 'darkmagenta')
        p = TicketPriority(name='Totally unknown priority')
        self.assertEqual(p.color, 'darkgray')


class TestTicket(TestCase):

    def test_str(self):
        t = Ticket(id=1, summary='Únicôde wôrks!')
        self.assertEqual(
            '{}'.format(t),
            '1-Únicôde wôrks!'
        )
    #
    # def test_update_api_ticket(self):
    #     board_name = 'Some Board Name'
    #     api_ticket = deepcopy(fixtures.API_SERVICE_TICKET)
    #     api_ticket['board']['name'] = board_name
    #
    #     mocks.service_api_update_ticket_call(api_ticket)
    #     mocks.service_api_get_ticket_call()
    #
    #     local_ticket = Ticket.objects.first()
    #     local_ticket.board_name = board_name
    #     local_ticket.closed_flag = True
    #     local_ticket.save()
    #
    #     updated_api_ticket = self.updater.update_api_ticket(local_ticket)
    #
    #     self.assertEqual(
    #         updated_api_ticket['board']['name'],
    #         local_ticket.board_name
    #     )
    #
    # def test_update_api_ticket_invalid_status(self):
    #     # Raises an exception if the ticket status isn't valid for the
    #     # ticket's board.
    #     print()
    #     print(Ticket.objects.first())
    #     print(ConnectWiseBoard.objects.all())
    #     print(BoardStatus.objects.all())
    #     print()
    #
    # def test_close_ticket(self):
    #     self.assertTrue(False)
    #
    # def test_close_ticket_no_closed_statuses(self):
    #     # Raises an exception if there are no available closed statuses for
    #     # the ticket's board.
    #     self.assertTrue(False)
