from djconnectwise.models import TicketPriority, BoardStatus
from model_mommy import mommy
from test_plus.test import TestCase
from djconnectwise.models import Ticket, InvalidStatusError, Sla, Calendar
from djconnectwise.models import MyCompanyOther
from unittest.mock import patch
from django.utils import timezone
from freezegun import freeze_time
import datetime

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
        Sla.objects.create(
            name="Standard SLA",
            default_flag=True,
            respond_hours=2,
            plan_within=8,
            resolution_hours=96,
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


class TestCalendar(ModelTestCase):

    def test_get_first_day(self):
        calendar = Calendar.objects.first()

        day, days = calendar.get_first_day(5)
        self.assertEqual(day, 0)
        self.assertEqual(days, 2)

        day, days = calendar.get_first_day(2)
        self.assertEqual(day, 2)
        self.assertEqual(days, 0)

        day, days = calendar.get_first_day(6)
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

    @freeze_time("2018-08-23 17:24:34", tz_offset=-7)
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

        self.assertEqual(
            str(ticket.sla_expire_date.astimezone(tz=None)),
            '2018-08-23 12:24:34-07:00'
            )
        self.assertEqual('respond', ticket.sla_stage)

    @freeze_time("2018-08-23 17:24:34", tz_offset=-7)
    def test_calculate_next_state_sla_expiry(self):
        board = self.connectwise_boards[0]
        old_status = board.board_statuses.get(name='New')
        ticket = Ticket.objects.create(
            summary='test',
            status=old_status,
            sla=Sla.objects.first(),
            priority=self.ticket_priorities[0],
            board=board,
            entered_date_utc=timezone.now()
        )
        ticket.calculate_sla_expiry()

        ticket.status = board.board_statuses.get(name='Scheduled')
        ticket.calculate_sla_expiry(old_status=old_status)

        self.assertEqual(
            str(ticket.sla_expire_date.astimezone(tz=None)),
            '2018-08-24 09:24:34-07:00'
            )
        self.assertEqual('plan', ticket.sla_stage)

    @freeze_time("2018-08-23 23:24:34", tz_offset=-7)
    def test_calculate_sla_expiry_overnight(self):
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

        self.assertEqual(
            str(ticket.sla_expire_date.astimezone(tz=None)),
            '2018-08-24 09:24:34-07:00'
            )

    @freeze_time("2018-08-23 17:24:34", tz_offset=-7)
    def test_calculate_sla_expiry_several_days(self):
        board = self.connectwise_boards[0]
        ticket = Ticket.objects.create(
            summary='test',
            status=board.board_statuses.get(name='In Progress'),
            sla=Sla.objects.first(),
            priority=self.ticket_priorities[0],
            board=board,
            entered_date_utc=timezone.now()
        )
        ticket.calculate_sla_expiry()

        self.assertEqual(
            str(ticket.sla_expire_date.astimezone(tz=None)),
            '2018-09-06 16:24:34-07:00'
            )

    @freeze_time("2018-08-25 15:24:34", tz_offset=0)
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

        self.assertEqual(
            str(ticket.sla_expire_date.astimezone(tz=None)),
            '2018-08-27 10:00:34-07:00'
            )

    @freeze_time("2018-08-23 17:24:34", tz_offset=-7)
    def test_resolve_sla(self):
        # Test entering a resolved state
        board = self.connectwise_boards[0]
        old_status = board.board_statuses.get(name='New')
        ticket = Ticket.objects.create(
            summary='test',
            status=old_status,
            sla=Sla.objects.first(),
            priority=self.ticket_priorities[0],
            board=board,
            entered_date_utc=timezone.now()
        )

        ticket.status = board.board_statuses.get(name='Completed')
        ticket.calculate_sla_expiry(old_status=old_status)

        self.assertFalse(ticket.sla_expire_date)
        self.assertEqual(ticket.sla_stage, 'resolved')

    @freeze_time("2018-08-23 17:24:34", tz_offset=-7)
    def test_sla_enter_waiting(self):
        board = self.connectwise_boards[0]
        old_status = board.board_statuses.get(name='New')
        ticket = Ticket.objects.create(
            summary='test',
            status=old_status,
            sla=Sla.objects.first(),
            priority=self.ticket_priorities[0],
            board=board,
            entered_date_utc=timezone.now()
        )

        ticket.status = board.board_statuses.get(name='Waiting For Client')
        ticket.calculate_sla_expiry(old_status=old_status)

        self.assertFalse(ticket.sla_expire_date)
        self.assertEqual(ticket.sla_stage, 'waiting')
        self.assertEqual(
            timezone.now(),
            ticket.do_not_escalate_date
            )

    @freeze_time("2018-08-23 17:24:34", tz_offset=-7)
    def test_sla_exit_waiting(self):
        board = self.connectwise_boards[0]
        entered_date_utc = timezone.now() - datetime.timedelta(hours=3)
        waiting_status = board.board_statuses.get(name='Waiting For Client')
        ticket = Ticket.objects.create(
            summary='test',
            status=waiting_status,
            sla=Sla.objects.first(),
            priority=self.ticket_priorities[0],
            board=board,
            entered_date_utc=entered_date_utc,
            do_not_escalate_date=timezone.now()-datetime.timedelta(hours=1)
        )

        ticket.status = board.board_statuses.get(name='New')
        ticket.calculate_sla_expiry(old_status=waiting_status)

        self.assertEqual(ticket.sla_stage, 'respond')
        self.assertEqual(ticket.minutes_waiting, 60)
        self.assertFalse(ticket.do_not_escalate_date)
        self.assertTrue(ticket.sla_expire_date)

    def test_sla_exit_waiting_out_of_hours(self):
        board = self.connectwise_boards[0]
        entered_date_utc = timezone.now()
        waiting_status = board.board_statuses.get(name='Waiting For Client')
        ticket = Ticket.objects.create(
            summary='test',
            status=waiting_status,
            sla=Sla.objects.first(),
            priority=self.ticket_priorities[0],
            board=board,
            entered_date_utc=entered_date_utc,
            do_not_escalate_date=timezone.now()
        )

        ticket.status = board.board_statuses.get(name='New')
        ticket.calculate_sla_expiry(old_status=waiting_status)

        self.assertEqual(ticket.sla_stage, 'respond')
        self.assertFalse(ticket.do_not_escalate_date)
        self.assertTrue(ticket.sla_expire_date)

    @freeze_time("2018-08-25 17:24:34", tz_offset=-7)
    def test_sla_exit_waiting_weekend(self):
        board = self.connectwise_boards[0]
        entered_date_utc = timezone.now() - datetime.timedelta(hours=4)
        waiting_status = board.board_statuses.get(name='Waiting For Client')
        ticket = Ticket.objects.create(
            summary='test',
            status=waiting_status,
            sla=Sla.objects.first(),
            priority=self.ticket_priorities[0],
            board=board,
            entered_date_utc=entered_date_utc,
            do_not_escalate_date=timezone.now() - datetime.timedelta(hours=2)
        )

        ticket.status = board.board_statuses.get(name='New')
        ticket.calculate_sla_expiry(old_status=waiting_status)

        self.assertEqual(ticket.sla_stage, 'respond')
        self.assertFalse(ticket.do_not_escalate_date)
        self.assertTrue(ticket.sla_expire_date)
        self.assertEqual(ticket.minutes_waiting, 0)

    def test_sla_exit_waiting_to_lower_status(self):
        board = self.connectwise_boards[0]
        name_this_var = timezone.now()
        waiting_status = board.board_statuses.get(name='Waiting For Client')
        ticket = Ticket.objects.create(
            summary='test',
            status=waiting_status,
            sla=Sla.objects.first(),
            priority=self.ticket_priorities[0],
            board=board,
            entered_date_utc=name_this_var,
            do_not_escalate_date=timezone.now(),
            date_responded_utc=name_this_var
        )

        ticket.status = board.board_statuses.get(name='New')
        ticket.calculate_sla_expiry(old_status=waiting_status)

        self.assertEqual(ticket.sla_stage, 'plan')

    def test_sla_exit_resolved_only_to_resolve(self):
        board = self.connectwise_boards[0]
        name_this_var = timezone.now()
        old_status = board.board_statuses.get(name='Completed')
        ticket = Ticket.objects.create(
            summary='test',
            status=old_status,
            sla=Sla.objects.first(),
            priority=self.ticket_priorities[0],
            board=board,
            entered_date_utc=name_this_var,
            do_not_escalate_date=timezone.now(),
            date_resolved_utc=name_this_var
        )

        ticket.status = board.board_statuses.get(name='In Progress')
        ticket.calculate_sla_expiry(old_status=old_status)

        self.assertEqual(ticket.sla_stage, 'resolve')

    @freeze_time("2018-08-23 12:12:12", tz_offset=-7)
    def test_get_sla_time(self):
        # Ticket._get_sla_time(self, start, end, calendar)
        board = self.connectwise_boards[0]
        start = timezone.now()
        end = start + datetime.timedelta(days=1)
        calendar = Calendar.objects.first()
        ticket = Ticket.objects.create(
            summary='test',
            status=board.board_statuses.get(name='New'),
            sla=Sla.objects.first(),
            priority=self.ticket_priorities[0],
            board=board,
        )

        sla_time = ticket._get_sla_time(start, end, calendar)
        self.assertEqual(sla_time, 540)

    @freeze_time("2018-08-23 12:12:12", tz_offset=-7)
    def test_get_sla_time_same_day(self):
        board = self.connectwise_boards[0]
        start = timezone.now()
        end = start + datetime.timedelta(hours=1)
        calendar = Calendar.objects.first()
        ticket = Ticket.objects.create(
            summary='test',
            status=board.board_statuses.get(name='New'),
            sla=Sla.objects.first(),
            priority=self.ticket_priorities[0],
            board=board,
            entered_date_utc=timezone.now()
        )

        sla_time = ticket._get_sla_time(start, end, calendar)
        self.assertEqual(sla_time, 60)

    @freeze_time("2018-08-25 12:00:00", tz_offset=-7)
    def test_get_sla_time_over_weeked(self):
        board = self.connectwise_boards[0]
        start = timezone.now()
        end = start + datetime.timedelta(days=2)
        calendar = Calendar.objects.first()
        ticket = Ticket.objects.create(
            summary='test',
            status=board.board_statuses.get(name='New'),
            sla=Sla.objects.first(),
            priority=self.ticket_priorities[0],
            board=board,
            entered_date_utc=timezone.now()
        )

        sla_time = ticket._get_sla_time(start, end, calendar)
        self.assertEqual(sla_time, 240)

    @freeze_time("2018-08-25 12:00:00", tz_offset=-7)
    def test_sla_get_time_same_day_weekend(self):
        board = self.connectwise_boards[0]
        start = timezone.now()
        end = start + datetime.timedelta(hours=2)
        calendar = Calendar.objects.first()
        ticket = Ticket.objects.create(
            summary='test',
            status=board.board_statuses.get(name='New'),
            sla=Sla.objects.first(),
            priority=self.ticket_priorities[0],
            board=board,
            entered_date_utc=timezone.now()
        )

        sla_time = ticket._get_sla_time(start, end, calendar)
        self.assertEqual(sla_time, 0)

    def test_lowest_possible_stage(self):
        board = self.connectwise_boards[0]
        ticket = Ticket.objects.create(
            summary='test',
            status=board.board_statuses.get(name='New'),
            sla=Sla.objects.first(),
            priority=self.ticket_priorities[0],
            board=board,
        )

        result = ticket._lowest_possible_stage('resolved')
        self.assertEqual('resolved', result)

        result = ticket._lowest_possible_stage('respond')
        self.assertEqual('respond', result)

        result = ticket._lowest_possible_stage('plan')
        self.assertEqual('plan', result)

        result = ticket._lowest_possible_stage('resolve')
        self.assertEqual('resolve', result)

        ticket.date_responded_utc = timezone.now()
        result = ticket._lowest_possible_stage('respond')
        self.assertEqual('plan', result)

        ticket.date_resplan_utc = timezone.now()
        result = ticket._lowest_possible_stage('respond')
        self.assertEqual('resolve', result)
