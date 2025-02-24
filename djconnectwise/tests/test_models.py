import datetime
from unittest.mock import patch

from djconnectwise.models import MyCompanyOther, Holiday, HolidayList, \
    Ticket, Calendar, TicketPriority, BoardStatus
from model_mommy import mommy
from test_plus.test import TestCase

ticket_statuses_names = [
    'New',
    'In Progress',
    'Scheduled',
    'Blocked',
    'Completed',
    'Waiting For Client',
    'Closed',
]
escalation_stages = [
    'NotResponded',
    'ResolutionPlan',
    'Responded',
    'NoEscalation',
    'Resolved',
    'NoEscalation',
    'Resolved'
]


class ModelTestCase(TestCase):

    def setUp(self):
        self.members = mommy.make_recipe(
            'djconnectwise.tests.member',
            _quantity=3
        )
        self.projects = mommy.make_recipe(
            'djconnectwise.tests.project',
            _quantity=4,
        )
        self.companies = mommy.make_recipe(
            'djconnectwise.tests.company',
            _quantity=2
        )
        self.ticket_priorities = mommy.make_recipe(
            'djconnectwise.tests.ticket_priority',
            _quantity=3
        )
        self.connectwise_boards = mommy.make_recipe(
            'djconnectwise.tests.connectwise_board',
            _quantity=3,
        )

        holiday_list = HolidayList.objects.create(
            name="Test List"
        )
        Holiday.objects.create(
            name="Test Holiday",
            all_day_flag=True,
            date=datetime.datetime(year=2017, day=12, month=12),
            holiday_list=holiday_list
        )
        calendar = Calendar.objects.create(
            name="Standard Office Hours",
            monday_start_time='08:00:00',
            monday_end_time='17:00:00',
            tuesday_start_time='08:00:00',
            tuesday_end_time='17:00:00',
            wednesday_start_time='08:00:00',
            wednesday_end_time='17:00:00',
            thursday_start_time='08:00:00',
            thursday_end_time='17:00:00',
            friday_start_time='08:00:00',
            friday_end_time='17:00:00',
            saturday_start_time=None,
            saturday_end_time=None,
            sunday_start_time=None,
            sunday_end_time=None,
            holiday_list=holiday_list
        )
        MyCompanyOther.objects.create(
            default_calendar=calendar
        )
        Calendar.objects.create()
        for i, s in enumerate(ticket_statuses_names):
            # All the statuses belong to the first board.
            BoardStatus.objects.create(
                name=s,
                sort_order=i,
                board=self.connectwise_boards[0],
                closed_status=True if s in ['Completed', 'Closed'] else False,
                escalation_status=escalation_stages[i],
                display_on_board=True,
                inactive=False,
            )


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


class TestBoard(ModelTestCase):
    def test_get_closed_status_prefers_closed(self):
        board = self.connectwise_boards[0]
        self.assertEqual(
            board.get_closed_status().name,
            'Closed'
        )

    def test_get_closed_status_any_closed(self):
        # Return some closed status if there's not a closed status called
        # 'Closed'
        board = self.connectwise_boards[0]
        board.board_statuses.filter(name='Closed').delete()
        closed_status = board.get_closed_status()
        self.assertTrue(closed_status.closed_status)
        self.assertNotEqual(
            closed_status.name,
            'Closed'
        )

    def test_get_closed_status_no_closed(self):
        # Return None if there's no closed statuses
        board = self.connectwise_boards[0]
        board.board_statuses.filter(closed_status=True).delete()
        closed_status = board.get_closed_status()
        self.assertEqual(closed_status, None)


class TestBoardStatus(ModelTestCase):
    def test_compare_lt(self):
        board = self.connectwise_boards[0]
        status_a = board.board_statuses[0]
        status_b = board.board_statuses[1]
        self.assertTrue(status_a < status_b)
        self.assertFalse(status_b < status_a)

    def test_compare_gt(self):
        board = self.connectwise_boards[0]
        status_a = board.board_statuses[0]
        status_b = board.board_statuses[1]
        self.assertTrue(status_b > status_a)
        self.assertFalse(status_a > status_b)

    def test_compare_none(self):
        board = self.connectwise_boards[0]
        status = board.board_statuses[0]
        self.assertFalse(None > status)
        self.assertFalse(status > None)
        self.assertFalse(None < status)
        self.assertFalse(status < None)


class TestCalendar(ModelTestCase):

    def test_get_first_day(self):
        calendar = Calendar.objects.first()

        day, days = calendar.get_first_day(
            datetime.datetime(year=2018, day=29, month=9))
        self.assertEqual(day, 0)
        self.assertEqual(days, 2)

        day, days = calendar.get_first_day(
            datetime.datetime(year=2018, day=19, month=9))
        self.assertEqual(day, 2)
        self.assertEqual(days, 0)

        day, days = calendar.get_first_day(
            datetime.datetime(year=2018, day=23, month=9))
        self.assertEqual(day, 0)
        self.assertEqual(days, 1)


class TestTicket(ModelTestCase):

    def test_str(self):
        t = Ticket(id=1, summary='Únicôde wôrks!')
        self.assertEqual(
            '{}'.format(t),
            '1-Únicôde wôrks!'
        )

    def test_save_checks_status(self):
        # Raises an exception if the ticket status isn't valid for the
        # ticket's board.
        ticket = Ticket.objects.create(
            summary='test',
            status=self.connectwise_boards[0].board_statuses.first(),
            board=self.connectwise_boards[0]
        )
        with patch('djconnectwise.models.logger') as mock_logging:
            ticket.save()  # Should not log
            self.assertFalse(mock_logging.warning.called)
        with patch('djconnectwise.models.logger') as mock_logging:
            ticket.board = self.connectwise_boards[1]
            ticket.save()  # Should log
            self.assertTrue(mock_logging.warning.called)

    def test_save_calls_update_cw_when_kwarg_passed(self):
        board = self.connectwise_boards[0]
        ticket = Ticket.objects.create(
            summary='test',
            status=board.board_statuses.first(),
            board=board
        )
        with patch('djconnectwise.api.'
                   'ServiceAPIClient') as mock_serviceapiclient:
            instance = mock_serviceapiclient.return_value
            # Call save with no 'update_cw' kwarg- our mock should NOT
            # be called
            ticket.save()
            self.assertFalse(instance.update_ticket.called)
            # Now call it with 'update_cw'
            ticket.save(update_cw=True, changed_fields={'summary': 'New'})
            self.assertTrue(instance.update_ticket.called)

    def test_update_cw(self):
        # Verify update_cw calls the API client
        board = self.connectwise_boards[0]
        ticket = Ticket.objects.create(
            summary='test',
            status=board.board_statuses.first(),
            board=board
        )
        with patch('djconnectwise.api.'
                   'ServiceAPIClient') as mock_serviceapiclient:
            instance = mock_serviceapiclient.return_value
            ticket.update_cw()
            self.assertTrue(instance.update_ticket.called)

    def test_close_ticket(self):
        # Verify close calls save.
        board = self.connectwise_boards[0]
        ticket = Ticket.objects.create(
            summary='test',
            status=board.board_statuses.first(),
            board=board
        )
        with patch.object(ticket, 'save') as mock_save:
            ticket.close()
            self.assertTrue(mock_save.called)
