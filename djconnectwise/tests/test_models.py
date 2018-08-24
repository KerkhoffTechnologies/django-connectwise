from djconnectwise.models import TicketPriority, BoardStatus
from model_mommy import mommy
from test_plus.test import TestCase
from djconnectwise.models import Ticket, InvalidStatusError, Sla, Calendar
from djconnectwise.models import MyCompanyOther
from unittest.mock import patch
from django.utils import timezone
from freezegun import freeze_time

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
    'Responded',
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
        Sla.objects.create(
            name="Standard SLA",
            default_flag=True,
            respond_hours=2,
            plan_within=4,
            resolution_hours=16,
            based_on='MyCalendar'
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
            sunday_end_time=None
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
            ticket.save(update_cw=True)
            self.assertTrue(instance.update_ticket_status.called)

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
            self.assertTrue(instance.update_ticket_status.called)

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

    def test_close_ticket_no_closed_statuses(self):
        # Raises an exception if there are no available closed statuses for
        # the ticket's board.
        board = self.connectwise_boards[0]
        board.board_statuses.filter(closed_status=True).delete()

        ticket = Ticket.objects.create(
            summary='test',
            status=board.board_statuses.first(),
            board=board
        )
        ticket.save()  # Should work
        with self.assertRaises(InvalidStatusError):
            ticket.close()

    @freeze_time("2018-08-23 15:24:34", tz_offset=0)
    def test_calculate_sla_expiry(self):
        board = self.connectwise_boards[0]
        ticket = Ticket.objects.create(
            summary='test',
            status=board.board_statuses.get(name='New'),
            sla=Sla.objects.first(),
            priority=self.ticket_priorities[0],
            board=board,
            entered_date_utc=timezone.now()
        )
        ticket.calculate_sla_expiry()

        self.assertTrue(False)

    @freeze_time("2018-08-26 15:24:34", tz_offset=0)
    def test_calculate_sla_expiry_out_of_hours(self):
        board = self.connectwise_boards[0]
        ticket = Ticket.objects.create(
            summary='test',
            status=board.board_statuses.get(name='New'),
            sla=Sla.objects.first(),
            priority=self.ticket_priorities[0],
            board=board,
            entered_date_utc=timezone.now()
        )
        ticket.calculate_sla_expiry()
        self.assertTrue(False)

    def test_sla_enter_waiting(self):
        board = self.connectwise_boards[0]
        ticket = Ticket.objects.create(
            summary='test',
            status=board.board_statuses.get(name='New'),
            sla=Sla.objects.first(),
            priority=self.ticket_priorities[0],
            board=board,
            entered_date_utc=timezone.now()
        )

        ticket.status = board.board_statuses.get(name='Waiting For Client')
        ticket.save()

        self.assertEqual(ticket.sla_stage, 'waiting')

    def test_sla_exit_waiting(self):
        board = self.connectwise_boards[0]
        entered_date_utc = timezone.now()
        ticket = Ticket.objects.create(
            summary='test',
            status=board.board_statuses.get(name='Waiting For Client'),
            sla=Sla.objects.first(),
            priority=self.ticket_priorities[0],
            board=board,
            entered_date_utc=entered_date_utc,
            do_not_escalate_date=timezone.now()
        )

        ticket.status = board.board_statuses.get(name='respond')
        ticket.save()

        self.assertEqual(ticket.sla_stage, 'NotResponded')
        self.assertEqual(None, self.do_not_escalate_date)
        self.assertTrue(sla_expire_date)

    def test_sla_exit_waiting_to_lower_status(self):
        board = self.connectwise_boards[0]
        name_this_var = timezone.now()
        ticket = Ticket.objects.create(
            summary='test',
            status=board.board_statuses.get(name='Waiting For Client'),
            sla=Sla.objects.first(),
            priority=self.ticket_priorities[0],
            board=board,
            entered_date_utc=name_this_var,
            do_not_escalate_date=timezone.now(),
            date_responded_utc=name_this_var
        )

        ticket.status = board.board_statuses.get(name='New')
        ticket.save()

        self.assertEqual(ticket.sla_stage, 'plan')

    def test_sla_exit_resolved_only_to_resolve(self):
        board = self.connectwise_boards[0]
        name_this_var = timezone.now()
        ticket = Ticket.objects.create(
            summary='test',
            status=board.board_statuses.get(name='Resolved'),
            sla=Sla.objects.first(),
            priority=self.ticket_priorities[0],
            board=board,
            entered_date_utc=name_this_var,
            do_not_escalate_date=timezone.now(),
            date_resolved_utc=name_this_var
        )

        ticket.status = board.board_statuses.get(name='Resolve')
        ticket.save()

        self.assertEqual(ticket.sla_stage, 'resolve')

    def test_get_sla_time(self):
        # Ticket._get_sla_time(self, start, end, calendar)

    def test_get_sla_time_same_day(self):
        self.assertTrue(False)

    def test_get_sla_time_over_weeked(self):
        pass

    def test_sla_get_time_same_day_weekend(self):
        pass

    def test_lowest_possible_stage(self):
        pass
