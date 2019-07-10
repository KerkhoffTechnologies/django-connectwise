import re
import logging
import urllib
import datetime
from django.conf import settings
from django.utils import timezone
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from django.core.exceptions import ObjectDoesNotExist

from . import api

logger = logging.getLogger(__name__)


PRIORITY_RE = re.compile(r'^Priority ([\d]+)')


class InvalidStatusError(Exception):
    pass


class SlaGoalsMixin(object):
    """
    Returns the fields relevant to SLA goals for models with SLA information
    """

    def get_stage_hours(self, stage):
        if stage == 'respond':
            return self.respond_hours
        elif stage == 'plan':
            return self.plan_within
        elif stage == 'resolve':
            return self.resolution_hours
        elif stage == 'waiting':
            return 0
        else:
            return None


class SyncJob(models.Model):
    start_time = models.DateTimeField(null=False)
    end_time = models.DateTimeField(blank=True, null=True)
    entity_name = models.CharField(max_length=100)
    added = models.PositiveIntegerField(null=True)
    updated = models.PositiveIntegerField(null=True)
    deleted = models.PositiveIntegerField(null=True)
    success = models.NullBooleanField()
    message = models.TextField(blank=True, null=True)
    sync_type = models.CharField(max_length=32, default='full')

    def duration(self):
        if self.start_time and self.end_time:
            return self.end_time - self.start_time


class AvailableConnectWiseBoardManager(models.Manager):
    """Return only active ConnectWise boards."""
    def get_queryset(self):
        return super().get_queryset().filter(inactive=False)


class ConnectWiseBoard(TimeStampedModel):
    name = models.CharField(max_length=255)
    inactive = models.BooleanField(default=False)

    objects = models.Manager()
    available_objects = AvailableConnectWiseBoardManager()

    class Meta:
        ordering = ('name',)
        verbose_name = 'ConnectWise board'

    def __str__(self):
        return self.name

    @property
    def board_statuses(self):
        return BoardStatus.available_objects.filter(board=self)

    def get_closed_status(self):
        """
        Find a closed status on the board. Prefer the status
        called "Closed", if such a one exists.
        """
        try:
            closed_status = self.board_statuses.get(
                name='Closed',
                closed_status=True,
            )
        except BoardStatus.DoesNotExist:
            # There's nothing called "Closed".
            # filter...first returns None if nothing is found.
            closed_status = self.board_statuses.filter(
                closed_status=True,
            ).first()
        return closed_status


class AvailableBoardStatusManager(models.Manager):
    """
    Return only statuses whose ConnectWise board is active, and whose
    inactive field is False.
    """
    def get_queryset(self):
        return super().get_queryset().filter(
            board__inactive=False, inactive=False
        )


class BoardStatus(TimeStampedModel):
    """
    Used for looking up the status/board id combination
    """
    CLOSED = 'Closed'

    ESCALATION_STATUSES = (
        ('NotResponded', 'Not Responded'),
        ('Responded', 'Responded'),
        ('ResolutionPlan', 'Resolution Plan'),
        ('Resolved', 'Resolved'),
        ('NoEscalation', 'No Escalation')
    )

    # For comparing Escalation Statuses
    ESCALATION_RANK = dict(
        zip(
            [type[0] for type in ESCALATION_STATUSES],
            [i for i in range(5)]
        )
    )

    name = models.CharField(blank=True, null=True, max_length=250)
    sort_order = models.PositiveSmallIntegerField()
    display_on_board = models.BooleanField()
    inactive = models.BooleanField()
    closed_status = models.BooleanField()
    board = models.ForeignKey('ConnectWiseBoard', on_delete=models.CASCADE)
    # Letting escalation_status allow blank/null rather than possibly having
    # and incorrect default value in some edge case
    escalation_status = models.CharField(
        max_length=20, choices=ESCALATION_STATUSES, db_index=True,
        blank=True, null=True
    )

    objects = models.Manager()
    available_objects = AvailableBoardStatusManager()

    class Meta:
        ordering = ('board__name', 'sort_order', 'name')
        verbose_name_plural = 'Board statuses'

    def is_non_escalation_status(self):
        return self.escalation_status == 'NoEscalation'

    def __str__(self):
        return '{}/{}'.format(self.board, self.name)

    def __lt__(self, other):
        if other is None:
            return False
        return self.ESCALATION_RANK.get(self.escalation_status) < \
            self.ESCALATION_RANK.get(other.escalation_status)

    def __gt__(self, other):
        if other is None:
            return False
        return self.ESCALATION_RANK.get(self.escalation_status) > \
            self.ESCALATION_RANK.get(other.escalation_status)

    def get_status_rank(self):
        return self.ESCALATION_RANK.get(self.escalation_status)


class Location(TimeStampedModel):
    name = models.CharField(max_length=30)
    where = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class RegularMemberManager(models.Manager):
    """Return members that aren't API members."""
    def get_queryset(self):
        return super().get_queryset().exclude(license_class='A')


class Member(TimeStampedModel):
    LICENSE_CLASSES = (
        ('F', 'Full license'),
        ('A', 'API license'),
    )
    identifier = models.CharField(  # This is the CW username
        max_length=15, blank=False, unique=True
    )
    first_name = models.CharField(max_length=30, blank=False)
    last_name = models.CharField(max_length=30, blank=False, null=True)
    office_email = models.EmailField(max_length=250)
    inactive = models.BooleanField(default=False)
    avatar = models.CharField(
        null=True, blank=True, max_length=250,
        verbose_name=_('Member Avatar'), help_text=_('Member Avatar')
    )
    license_class = models.CharField(
        blank=True, null=True, max_length=20,
        choices=LICENSE_CLASSES, db_index=True
    )

    objects = models.Manager()
    regular_objects = RegularMemberManager()

    class Meta:
        ordering = ('first_name', 'last_name')

    def __str__(self):
        return '{} {}'.format(self.first_name,
                              self.last_name if self.last_name else '')

    def get_initials(self):
        name_segs = str(self).split(' ')
        initial = ''
        for seg in name_segs:
            seg = seg.strip()
            initial += seg[:1]

        return initial


class AvailableCompanyManager(models.Manager):
    """Return only companies whose deleted_flag isn't true."""
    def get_queryset(self):
        return super().get_queryset().filter(deleted_flag=False)


class Company(TimeStampedModel):
    name = models.CharField(blank=True, null=True, max_length=250)
    identifier = models.CharField(
        blank=True, null=True, max_length=250)
    phone_number = models.CharField(blank=True, null=True, max_length=250)
    fax_number = models.CharField(blank=True, null=True, max_length=250)
    address_line1 = models.CharField(blank=True, null=True, max_length=250)
    address_line2 = models.CharField(blank=True, null=True, max_length=250)
    city = models.CharField(blank=True, null=True, max_length=250)
    state_identifier = models.CharField(blank=True, null=True, max_length=250)
    zip = models.CharField(blank=True, null=True, max_length=250)
    country = models.CharField(blank=True, null=True, max_length=250)
    website = models.CharField(blank=True, null=True, max_length=250)
    market = models.CharField(blank=True, null=True, max_length=250)
    defaultcontactid = models.IntegerField(blank=True, null=True)
    defaultbillingcontactid = models.IntegerField(blank=True, null=True)
    updatedby = models.CharField(blank=True, null=True, max_length=250)
    lastupdated = models.CharField(blank=True, null=True, max_length=250)
    deleted_flag = models.BooleanField(default=False)
    calendar = models.ForeignKey(
        'Calendar',
        blank=True,
        null=True,
        on_delete=models.SET_NULL
        )
    status = models.ForeignKey(
        'CompanyStatus',
        blank=True,
        null=True,
        on_delete=models.SET_NULL
        )
    company_type = models.ForeignKey(
        'CompanyType',
        blank=True,
        null=True,
        on_delete=models.SET_NULL
        )
    territory = models.ForeignKey(
        'Territory',
        blank=True,
        null=True,
        on_delete=models.SET_NULL
    )

    objects = models.Manager()
    available_objects = AvailableCompanyManager()

    class Meta:
        verbose_name_plural = 'companies'
        ordering = ('identifier', )

    def __str__(self):
        return self.get_identifier() or ''

    def get_identifier(self):
        return self.identifier


class CompanyStatus(models.Model):
    name = models.CharField(max_length=50)
    default_flag = models.BooleanField()
    inactive_flag = models.BooleanField()
    notify_flag = models.BooleanField()
    dissalow_saving_flag = models.BooleanField()
    notification_message = models.CharField(
        max_length=500,
        blank=True,
        null=True
    )
    custom_note_flag = models.BooleanField()
    cancel_open_tracks_flag = models.BooleanField()
    track_id = models.PositiveSmallIntegerField(blank=True, null=True)

    class Meta:
        verbose_name_plural = 'Company statuses'

    def __str__(self):
        return self.name


class CompanyType(models.Model):
    name = models.CharField(max_length=50)
    vendor_flag = models.BooleanField()

    class Meta:
        ordering = ('name', )

    def __str__(self):
        return self.name


class MyCompanyOther(models.Model):
    default_calendar = models.ForeignKey(
        'Calendar',
        blank=True,
        null=True,
        on_delete=models.SET_NULL
        )


class Calendar(models.Model):

    START_TIME = '_start_time'
    END_TIME = '_end_time'

    name = models.CharField(max_length=250)
    holiday_list = models.ForeignKey(
        'HolidayList', on_delete=models.SET_NULL, blank=True, null=True)
    monday_start_time = models.TimeField(auto_now=False, auto_now_add=False,
                                         blank=True, null=True)
    monday_end_time = models.TimeField(auto_now=False, auto_now_add=False,
                                       blank=True, null=True)
    tuesday_start_time = models.TimeField(auto_now=False, auto_now_add=False,
                                          blank=True, null=True)
    tuesday_end_time = models.TimeField(auto_now=False, auto_now_add=False,
                                        blank=True, null=True)
    wednesday_start_time = models.TimeField(auto_now=False, auto_now_add=False,
                                            blank=True, null=True)
    wednesday_end_time = models.TimeField(auto_now=False, auto_now_add=False,
                                          blank=True, null=True)
    thursday_start_time = models.TimeField(auto_now=False, auto_now_add=False,
                                           blank=True, null=True)
    thursday_end_time = models.TimeField(auto_now=False, auto_now_add=False,
                                         blank=True, null=True)
    friday_start_time = models.TimeField(auto_now=False, auto_now_add=False,
                                         blank=True, null=True)
    friday_end_time = models.TimeField(auto_now=False, auto_now_add=False,
                                       blank=True, null=True)
    saturday_start_time = models.TimeField(auto_now=False, auto_now_add=False,
                                           blank=True, null=True)
    saturday_end_time = models.TimeField(auto_now=False, auto_now_add=False,
                                         blank=True, null=True)
    sunday_start_time = models.TimeField(auto_now=False, auto_now_add=False,
                                         blank=True, null=True)
    sunday_end_time = models.TimeField(auto_now=False, auto_now_add=False,
                                       blank=True, null=True)

    def __str__(self):
        return self.name

    def get_day_hours(self, is_start, day):
        if is_start:
            time = self.START_TIME
        else:
            time = self.END_TIME

        days = [
            'monday',
            'tuesday',
            'wednesday',
            'thursday',
            'friday',
            'saturday',
            'sunday'
        ]
        return getattr(self, "{}{}".format(days[day], time), None)

    def get_first_day(self, start):
        """
        For getting the first weekday, and the days until that day, from the
        given start day that has a start and end time.
        """
        start_day = start.weekday()
        days = 0
        while True:
            day = self.get_day_hours(True, start_day)
            if day and \
                    not self.is_holiday(datetime.timedelta(days=days) + start):
                return start_day, days
            start_day = (start_day + 1) % 7
            days += 1
            if days >= 7:
                # Calendar has no hours on any day. This case can also occur
                # if a calendar has seven consecutive holidays.
                return None, None

    def is_holiday(self, date):
        current_day = date.date()
        try:
            holiday = self.holiday_list.holiday_set.filter(date=current_day)
            # Decided to go with filter, and test whether the list is empty or
            # not. Rather than get, and deal with the possibility of
            # DoesNotExist and MultipleObjectsReturned.
        except AttributeError:
            # No holiday list on this calendar
            return False
        if holiday:
            return True
        # Returning False instead of None
        return False

    def get_sla_time(self, start, end):
        # Get the sla-minutes between two dates using the given calendar
        minutes = 0
        day_of_week = start.weekday()
        start_time = datetime.timedelta(hours=start.hour,
                                        minutes=start.minute)

        # Get sla minutes for first day
        start_day_end_time = self.get_day_hours(False, start.weekday())

        if start_day_end_time and \
                not self.is_holiday(timezone.now().astimezone(tz=None)):
            end_of_day = datetime.timedelta(hours=start_day_end_time.hour,
                                            minutes=start_day_end_time.minute)
        else:
            end_of_day = None

        if start.date() == end.date():

            if end_of_day:

                end_time = min(start_day_end_time, end.time())
                end_time_delta = datetime.timedelta(
                    hours=end_time.hour,
                    minutes=end_time.minute
                )

                minutes = (end_time_delta - start_time).total_seconds() / 60
            # return sla time between start and end of day/end time, or zero
            # if start and end was outside of work hours
            return max(minutes, 0)
        else:
            if end_of_day and \
                    not self.is_holiday(timezone.now().astimezone(tz=None)):
                first_day_minutes = (end_of_day - start_time).total_seconds() \
                    / 60
            else:
                first_day_minutes = 0

            sla_minutes = first_day_minutes if first_day_minutes >= 0 else 0
            current = start + datetime.timedelta(days=1)
            day_of_week = (day_of_week + 1) % 7

            while current.date() != end.date():
                start_of_day = self.get_day_hours(True, day_of_week)
                if start_of_day and not self.is_holiday(current):
                    start_of_day = datetime.timedelta(
                        hours=start_of_day.hour,
                        minutes=start_of_day.minute)
                    end_of_day = self.get_day_hours(False, day_of_week)
                    end_of_day = datetime.timedelta(
                        hours=end_of_day.hour,
                        minutes=end_of_day.minute)
                else:
                    # This is a day with no hours, continue to next day
                    day_of_week = (day_of_week + 1) % 7
                    current = current + datetime.timedelta(days=1)
                    continue

                minutes = (end_of_day - start_of_day).total_seconds() / 60
                # 24 hour calendar, minutes are full day
                todays_minutes = minutes if minutes >= 0 else 1440
                sla_minutes = sla_minutes + todays_minutes
                day_of_week = (day_of_week + 1) % 7
                current = current + datetime.timedelta(days=1)

            end_of_day = self.get_day_hours(False, end.weekday())

            if end_of_day:
                end_of_day = datetime.timedelta(
                    hours=end_of_day.hour,
                    minutes=end_of_day.minute)

                end_time = datetime.timedelta(
                    hours=end.hour,
                    minutes=end.minute) if \
                    self.get_day_hours(False, end.weekday()) > \
                    end.time() else end_of_day

                # get sla_minutes for last day
                start_of_day = self.get_day_hours(True, end.weekday())
                start_of_day = datetime.timedelta(hours=start_of_day.hour,
                                                  minutes=start_of_day.minute)

                last_day_minutes = (end_time - start_of_day).total_seconds() \
                    / 60
                minutes = last_day_minutes if last_day_minutes >= 0 else 0
            else:
                minutes = 0
            sla_minutes += minutes
            return sla_minutes

    def next_phase_expiry(self, sla_hours, ticket):

        start = ticket.entered_date_utc.astimezone(tz=None)

        # Start counting from the start of the next business day if the
        # ticket was created on a weekend
        day_of_week, days = self.get_first_day(start)

        if day_of_week is None and days is None:
            ticket.sla_expire_date = None
            return

        sla_minutes, days, minutes, sla_start = self.get_sla_start(
                                               sla_hours,
                                               ticket.minutes_waiting,
                                               start,
                                               day_of_week,
                                               days
                                              )

        # Advance day by day, reducing the sla_minutes by the time in
        # each working day.
        # When minutes goes below zero, add the amount of time left on it
        # that day to the start time of that day, giving you the due date
        while sla_minutes >= 0:
            day_of_week = (day_of_week + 1) % 7
            days += 1

            start_of_day = self.get_day_hours(True, day_of_week)
            if start_of_day and \
                not self.is_holiday(
                                    datetime.timedelta(days=days) + start):
                start_of_day = datetime.timedelta(hours=start_of_day.hour,
                                                  minutes=start_of_day.minute)
                end_of_day = self.get_day_hours(False, day_of_week)
                end_of_day = datetime.timedelta(hours=end_of_day.hour,
                                                minutes=end_of_day.minute)
            else:
                # This is a day with no hours, continue to next day
                continue

            minutes = (end_of_day - start_of_day).total_seconds() / 60
            # 24 hour calendar, minutes are full day
            todays_minutes = minutes if minutes >= 0 else 1440
            sla_minutes = sla_minutes - todays_minutes

        # sla_minutes went below zero so we know that day is the expiry
        # Add the minutes back to sla_minutes and add sla minutes to the
        # start of that day
        sla_minutes = sla_minutes + minutes
        self.set_sla_end(sla_start, days, day_of_week, sla_minutes, ticket)

    def get_sla_start(self, sla_hours, waiting_min, start, day_of_week, days):
        if days > 0:
            start = start + datetime.timedelta(days=days)
            start_of_day = self.get_day_hours(True, day_of_week)
            start = start.replace(
                hour=start_of_day.hour,
                minute=start_of_day.minute
            )
            days = 0

        start_date = datetime.timedelta(hours=start.hour,
                                        minutes=start.minute)

        sla_minutes = (sla_hours * 60) + waiting_min

        end_of_day = self.get_day_hours(False, day_of_week)
        end_of_day = datetime.timedelta(hours=end_of_day.hour,
                                        minutes=end_of_day.minute)
        first_day_minutes = (end_of_day - start_date).total_seconds() / 60

        # If created outside of work hours, take no minutes off and start
        # taking time off next work day
        minutes = first_day_minutes if first_day_minutes >= 0 else 0
        sla_minutes = sla_minutes - minutes

        return sla_minutes, days, minutes, start

    def set_sla_end(self, start, days, day_of_week, sla_minutes, ticket):
        expiry_date = start + datetime.timedelta(days=days)

        if days == 0:
            sla_expire_time = start + datetime.timedelta(minutes=sla_minutes)
            expiry_date = expiry_date.replace(
                hour=sla_expire_time.hour, minute=sla_expire_time.minute)
        else:
            sla_expire_time = self.get_day_hours(True, day_of_week)
            expiry_date = expiry_date.replace(
                hour=sla_expire_time.hour, minute=sla_expire_time.minute) + \
                datetime.timedelta(minutes=sla_minutes)

        ticket.sla_expire_date = expiry_date.astimezone(tz=timezone.utc)


class Holiday(models.Model):
    name = models.CharField(max_length=200)
    all_day_flag = models.BooleanField(default=False)
    date = models.DateField(
                            blank=True,
                            null=True,
                            auto_now=False,
                            auto_now_add=False
                            )
    start_time = models.TimeField(
                                  auto_now=False,
                                  auto_now_add=False,
                                  blank=True,
                                  null=True
                                  )
    end_time = models.TimeField(
                                auto_now=False,
                                auto_now_add=False,
                                blank=True,
                                null=True
                                )
    holiday_list = models.ForeignKey(
        'HolidayList', on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class HolidayList(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class ScheduleType(models.Model):
    name = models.CharField(max_length=50)
    identifier = models.CharField(max_length=1)

    class Meta:
        ordering = ('name', )

    def __str__(self):
        return self.name


class ScheduleStatus(models.Model):
    name = models.CharField(max_length=30)

    class Meta:
        verbose_name_plural = 'Schedule statuses'

    def __str__(self):
        return self.name


class ScheduleEntry(models.Model):
    name = models.CharField(max_length=250, blank=True, null=True)
    expected_date_start = models.DateTimeField(blank=True, null=True)
    expected_date_end = models.DateTimeField(blank=True, null=True)
    done_flag = models.BooleanField(default=False)

    ticket_object = models.ForeignKey(
        'Ticket',
        blank=True,
        null=True,
        on_delete=models.CASCADE
    )
    activity_object = models.ForeignKey(
        'Activity',
        blank=True,
        null=True,
        on_delete=models.CASCADE
    )
    member = models.ForeignKey('Member', on_delete=models.CASCADE)
    where = models.ForeignKey(
        'Location',
        blank=True,
        null=True,
        on_delete=models.SET_NULL
    )
    status = models.ForeignKey(
        'ScheduleStatus',
        blank=True,
        null=True,
        on_delete=models.SET_NULL
    )
    schedule_type = models.ForeignKey(
        'ScheduleType',
        blank=True,
        null=True,
        on_delete=models.SET_NULL
    )

    class Meta:
        verbose_name_plural = 'Schedule entries'
        ordering = ('name', )

    def __str__(self):
        return self.name or ''

    def delete_entry(self):
        """
        Send Delete request to ConnectWise for this entry
        """
        schedule_client = api.ScheduleAPIClient()
        return schedule_client.delete_schedule_entry(self.id)


class Territory(models.Model):
    name = models.CharField(max_length=250, blank=True, null=True)

    class Meta:
        verbose_name_plural = 'Territories'
        ordering = ('name', )

    def __str__(self):
        return self.name


class TimeEntry(models.Model):
    CHARGE_TYPES = (
        ('ServiceTicket', "Service Ticket"),
        ('ProjectTicket', "Project Ticket"),
        ('ChargeCode', "Charge Code"),
        ('Activity', "Activity")
    )
    BILL_TYPES = (
        ('Billable', "Billable"),
        ('DoNotBill', "Do Not Bill"),
        ('NoCharge', "No Charge"),
    )

    class Meta:
        verbose_name_plural = 'Time entries'
        ordering = ('-time_start', 'id')

    def __str__(self):
        return str(self.id) or ''

    actual_hours = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=9)
    billable_option = models.CharField(choices=BILL_TYPES, max_length=250)
    charge_to_type = models.CharField(choices=CHARGE_TYPES, max_length=250)
    hours_deduct = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=9)
    internal_notes = models.TextField(blank=True, null=True, max_length=2000)
    notes = models.TextField(blank=True, null=True, max_length=2000)
    time_start = models.DateTimeField(blank=True, null=True)
    time_end = models.DateTimeField(blank=True, null=True)

    detail_description_flag = models.BooleanField(default=False)
    internal_analysis_flag = models.BooleanField(default=False)
    resolution_flag = models.BooleanField(default=False)

    email_resource_flag = models.BooleanField(default=False)
    email_contact_flag = models.BooleanField(default=False)
    email_cc_flag = models.BooleanField(default=False)

    charge_to_id = models.ForeignKey(
        'Ticket', blank=True, null=True, on_delete=models.CASCADE)
    company = models.ForeignKey(
        'Company', blank=True, null=True, on_delete=models.CASCADE)
    member = models.ForeignKey(
        'Member', blank=True, null=True, on_delete=models.CASCADE)


class AvailableBoardTeamManager(models.Manager):
    """Return only teams whose ConnectWise board is active."""
    def get_queryset(self):
        return super().get_queryset().filter(board__inactive=False)


class Team(TimeStampedModel):
    name = models.CharField(max_length=30)
    board = models.ForeignKey('ConnectWiseBoard', on_delete=models.CASCADE)
    members = models.ManyToManyField('Member')

    objects = models.Manager()
    available_objects = AvailableBoardTeamManager()

    class Meta:
        verbose_name_plural = 'Teams'
        ordering = ('name', 'id')

    def __str__(self):
        return '{}/{}'.format(self.board, self.name)


class TicketPriority(TimeStampedModel):
    name = models.CharField(max_length=50, blank=False)
    # ConnectWise doesn't always return sort and color- not sure why.
    # Sort will be None in this circumstance- dependent code should handle it.
    sort = models.PositiveSmallIntegerField(null=True)
    # Color will be a property that tries to guess at a sensible value.
    _color = models.CharField(
        max_length=50, null=True, blank=True, db_column='color'
    )

    DEFAULT_COLORS = {
        '1': 'red',
        '2': 'orange',
        '3': 'yellow',
        '4': 'white',
        '5': 'darkmagenta',
    }
    DEFAULT_COLOR = 'darkgray'

    class Meta:
        verbose_name_plural = 'ticket priorities'
        ordering = ('sort', 'name', )

    def __str__(self):
        return self.name

    @property
    def color(self):
        """
        If a color has been set, then return it. Otherwise if the name
        matches the common format ("Priority X - ..."), then return
        something sensible based on values seen in the wild.
        """
        if self._color == "Custom":
            return self.DEFAULT_COLOR
        elif self._color:
            return self._color
        else:
            prio_number = None
            prio_match = PRIORITY_RE.match(self.name)
            if prio_match:
                prio_number = prio_match.group(1)
            return TicketPriority.DEFAULT_COLORS.get(
                prio_number,
                TicketPriority.DEFAULT_COLOR
            )

    @color.setter
    def color(self, color):
        self._color = color


class ProjectStatus(TimeStampedModel):
    name = models.CharField(max_length=30)
    default_flag = models.BooleanField(default=False)
    inactive_flag = models.BooleanField(default=False)
    closed_flag = models.BooleanField(default=False)

    class Meta:
        ordering = ('name', )
        verbose_name_plural = 'Project statuses'

    def __str__(self):
        return self.name


class AvailableProjectManager(models.Manager):
    """
    Return only projects whose status closed field is False.
    """
    def get_queryset(self):
        return super().get_queryset().filter(
            status__closed_flag=False,
        )


class Project(TimeStampedModel):
    name = models.CharField(max_length=200)
    actual_hours = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=9)
    budget_hours = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=9)
    scheduled_hours = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=9)
    actual_start = models.DateField(blank=True, null=True)
    actual_end = models.DateField(blank=True, null=True)
    estimated_start = models.DateField(blank=True, null=True)
    estimated_end = models.DateField(blank=True, null=True)

    status = models.ForeignKey(
        'ProjectStatus', blank=True, null=True, on_delete=models.SET_NULL)
    manager = models.ForeignKey(
        'Member',
        blank=True,
        null=True,
        related_name='project_manager',
        on_delete=models.SET_NULL
    )

    objects = models.Manager()
    available_objects = AvailableProjectManager()

    class Meta:
        ordering = ('name', )

    def __str__(self):
        return self.name or ''


class OpportunityStage(TimeStampedModel):
    name = models.CharField(max_length=50)

    class Meta:
        ordering = ('name', )

    def __str__(self):
        return self.name


class AvailableOpportunityStatusManager(models.Manager):
    """
    Return only Opportunity Statuses whose inactive field is False.
    """
    def get_queryset(self):
        return super().get_queryset().filter(
            inactive_flag=False
        )


class OpportunityStatus(TimeStampedModel):
    name = models.CharField(max_length=30)
    won_flag = models.BooleanField(default=False)
    lost_flag = models.BooleanField(default=False)
    closed_flag = models.BooleanField(default=False)
    inactive_flag = models.BooleanField(default=False)

    objects = models.Manager()
    available_objects = AvailableOpportunityStatusManager()

    class Meta:
        ordering = ('name', )
        verbose_name_plural = 'Opportunity statuses'

    def __str__(self):
        return self.name


class OpportunityPriority(TimeStampedModel):
    name = models.CharField(max_length=50)

    class Meta:
        ordering = ('name', )
        verbose_name_plural = 'opportunity priorities'

    def __str__(self):
        return self.name


class OpportunityType(TimeStampedModel):
    description = models.CharField(max_length=50)
    inactive_flag = models.BooleanField(default=False)

    class Meta:
        ordering = ('description', )

    def __str__(self):
        return self.description


class Opportunity(TimeStampedModel):
    business_unit_id = models.IntegerField(null=True)
    closed_date = models.DateTimeField(blank=True, null=True)
    customer_po = models.CharField(max_length=100, blank=True, null=True)
    date_became_lead = models.DateTimeField(blank=True, null=True)
    expected_close_date = models.DateField()
    location_id = models.IntegerField()
    name = models.CharField(max_length=100)
    notes = models.TextField(blank=True, null=True)
    pipeline_change_date = models.DateTimeField(blank=True, null=True)
    probability = models.ForeignKey('SalesProbability',
                                    blank=True, null=True,
                                    related_name='sales_probability',
                                    on_delete=models.SET_NULL)
    source = models.CharField(max_length=100, blank=True, null=True)

    closed_by = models.ForeignKey('Member',
                                  blank=True, null=True,
                                  related_name='opportunity_closed_by',
                                  on_delete=models.SET_NULL)
    company = models.ForeignKey('Company', blank=True, null=True,
                                related_name='company_opportunities',
                                on_delete=models.SET_NULL)
    primary_sales_rep = models.ForeignKey('Member',
                                          blank=True, null=True,
                                          related_name='opportunity_primary',
                                          on_delete=models.SET_NULL)
    priority = models.ForeignKey('OpportunityPriority',
                                 on_delete=models.SET_NULL, null=True)
    stage = models.ForeignKey('OpportunityStage', on_delete=models.CASCADE)
    status = models.ForeignKey('OpportunityStatus', blank=True, null=True,
                               on_delete=models.SET_NULL)
    secondary_sales_rep = models.ForeignKey(
        'Member',
        blank=True, null=True,
        related_name='opportunity_secondary',
        on_delete=models.SET_NULL)
    opportunity_type = models.ForeignKey('OpportunityType',
                                         blank=True, null=True,
                                         on_delete=models.SET_NULL)

    class Meta:
        ordering = ('name', )
        verbose_name_plural = 'Opportunities'

    def __str__(self):
        return self.name

    def get_connectwise_url(self):
        params = dict(
            recordType='OpportunityFv',
            recid=self.id,
            companyName=settings.CONNECTWISE_CREDENTIALS['company_id']
        )
        return '{}/{}?{}'.format(
            settings.CONNECTWISE_SERVER_URL,
            settings.CONNECTWISE_TICKET_PATH,
            urllib.parse.urlencode(params)
        )

    def save(self, *args, **kwargs):
        """
        Save the object.

        If update_cw as a kwarg is True, then update ConnectWise with changes.
        """
        update_cw = kwargs.pop('update_cw', False)
        super().save(*args, **kwargs)
        if update_cw:
            self.update_cw()

    def update_cw(self):
        """
        Send ticket status and closed_flag updates to ConnectWise.
        """
        sales_client = api.SalesAPIClient()
        return sales_client.update_opportunity_stage(
            self.id, self.stage
        )


class Ticket(TimeStampedModel):
    RECORD_TYPES = (
        ('ServiceTicket', "Service Ticket"),
        ('ProjectTicket', "Project Ticket"),
        ('ProjectIssue', "Project Issue"),
    )

    BILL_TIME_TYPES = (
        ('Billable', "Billable"),
        ('DoNotBill', "Do Not Bill"),
        ('NoCharge', "No Charge"),
        ('NoDefault', "No Default")
    )

    RESPOND = 'respond'
    PLAN = 'plan'
    RESOLVE = 'resolve'
    RESOLVED = 'resolved'
    WAITING = 'waiting'

    SLA_STAGE = (
        (RESPOND, "Respond"),
        (PLAN, "Plan"),
        (RESOLVE, "Resolve"),
        (RESOLVED, "Resolved"),
        (WAITING, "Waiting"),
    )

    STAGE_RANK = dict(
        zip(
            [i for i in range(5)],
            [type[0] for type in SLA_STAGE]
        )
    )

    actual_hours = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=9)
    agreement_id = models.IntegerField(blank=True, null=True)
    approved = models.NullBooleanField(blank=True, null=True)
    budget_hours = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=9)
    closed_by = models.CharField(blank=True, null=True, max_length=250)
    closed_date_utc = models.DateTimeField(blank=True, null=True)
    closed_flag = models.NullBooleanField(blank=True, null=True)
    customer_updated = models.BooleanField(default=False)
    date_resolved_utc = models.DateTimeField(blank=True, null=True)
    date_resplan_utc = models.DateTimeField(blank=True, null=True)
    date_responded_utc = models.DateTimeField(blank=True, null=True)
    entered_date_utc = models.DateTimeField(blank=True, null=True)
    has_child_ticket = models.NullBooleanField()
    impact = models.CharField(blank=True, null=True, max_length=250)
    is_in_sla = models.NullBooleanField(blank=True, null=True)
    last_updated_utc = models.DateTimeField(blank=True, null=True)
    parent_ticket_id = models.IntegerField(blank=True, null=True)
    record_type = models.CharField(blank=True, null=True,
                                   max_length=250, choices=RECORD_TYPES,
                                   db_index=True)
    required_date_utc = models.DateTimeField(blank=True, null=True)
    respond_mins = models.IntegerField(blank=True, null=True)
    resolve_mins = models.IntegerField(blank=True, null=True)
    resources = models.CharField(blank=True, null=True, max_length=250)
    res_plan_mins = models.IntegerField(blank=True, null=True)
    severity = models.CharField(blank=True, null=True, max_length=250)
    site_name = models.CharField(blank=True, null=True, max_length=250)
    source = models.CharField(blank=True, null=True, max_length=250)
    summary = models.CharField(blank=True, null=True, max_length=250)
    updated_by = models.CharField(blank=True, null=True, max_length=250)
    sla_expire_date = models.DateTimeField(blank=True, null=True)
    do_not_escalate_date = models.DateTimeField(blank=True, null=True)
    sla_stage = models.CharField(blank=True, null=True,
                                 max_length=250, choices=SLA_STAGE,
                                 db_index=True)
    minutes_waiting = models.PositiveIntegerField(default=0)
    bill_time = models.CharField(blank=True, null=True,
                                 max_length=20, choices=BILL_TIME_TYPES)
    automatic_email_cc_flag = models.BooleanField(default=False)
    automatic_email_contact_flag = models.BooleanField(default=False)
    automatic_email_resource_flag = models.BooleanField(default=False)

    board = models.ForeignKey(
        'ConnectwiseBoard', blank=True, null=True, on_delete=models.CASCADE)
    company = models.ForeignKey(
        'Company', blank=True, null=True, related_name='company_tickets',
        on_delete=models.SET_NULL)
    location = models.ForeignKey(
        'Location', blank=True, null=True, related_name='location_tickets',
        on_delete=models.SET_NULL)
    members = models.ManyToManyField(
        'Member', through='ScheduleEntry',
        related_name='member_tickets')
    owner = models.ForeignKey(
        'Member', blank=True, null=True, on_delete=models.SET_NULL)
    priority = models.ForeignKey(
        'TicketPriority', blank=True, null=True, on_delete=models.SET_NULL)
    project = models.ForeignKey(
        'Project', blank=True, null=True, related_name='project_tickets',
        on_delete=models.CASCADE)
    status = models.ForeignKey(
        'BoardStatus', blank=True, null=True, related_name='status_tickets',
        on_delete=models.SET_NULL)
    team = models.ForeignKey(
        'Team', blank=True, null=True, related_name='team_tickets',
        on_delete=models.SET_NULL)
    sla = models.ForeignKey(
        'Sla', blank=True, null=True, related_name='tickets',
        on_delete=models.SET_NULL)
    type = models.ForeignKey(
        'Type', blank=True, null=True, related_name='type_tickets',
        on_delete=models.SET_NULL)
    sub_type = models.ForeignKey(
        'Subtype', blank=True, null=True, related_name='subtype_tickets',
        on_delete=models.SET_NULL)
    sub_type_item = models.ForeignKey(
        'Item', blank=True, null=True, related_name='item_tickets',
        on_delete=models.SET_NULL)

    class Meta:
        verbose_name = 'Ticket'
        verbose_name_plural = 'Tickets'
        ordering = ('summary', )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state_manager = StateMachineManager
        state_class = self.state_manager.get(self.sla_stage)
        self.sla_state = state_class(self) if state_class else None

    def __str__(self):
        return '{}-{}'.format(self.id, self.summary)

    def time_remaining(self):
        time_remaining = self.budget_hours
        if self.budget_hours and self.actual_hours:
            time_remaining = self.budget_hours - self.actual_hours
        return time_remaining

    def get_connectwise_url(self):
        params = dict(
            locale='en_US',
            recordType='ServiceFv',
            recid=self.id,
            companyName=settings.CONNECTWISE_CREDENTIALS['company_id']
        )
        return '{}/{}?{}'.format(
            settings.CONNECTWISE_SERVER_URL,
            settings.CONNECTWISE_TICKET_PATH,
            urllib.parse.urlencode(params)
        )

    def save(self, *args, **kwargs):
        """
        Save the object.

        If update_cw as a kwarg is True, then update ConnectWise with changes.
        """
        self._warn_invalid_status()

        update_cw = kwargs.pop('update_cw', False)
        super().save(*args, **kwargs)
        if update_cw:
            self.update_cw()

    def _warn_invalid_status(self):
        """
        Warn if the status doesn't belong to the board. It seems that
        ConnectWise isn't particularly strict about enforcing that a ticket's
        status is valid for the ticket's board, so we won't enforce this.

        If status or board are None, then don't bother, since this can happen
        during sync jobs and it would be a lot of work to enforce at all the
        right times.
        """
        if self.status and self.board and self.status.board != self.board:
            logger.warning(
                "For ticket {}, {} (ID {}) is not a valid status for the "
                "ticket's ConnectWise board ({}, ID {}).".
                format(
                    self.id,
                    self.status.name,
                    self.status.id,
                    self.board,
                    self.board.id,
                )
            )

    def update_cw(self):
        """
        Send ticket status or priority and closed_flag updates to ConnectWise.
        """
        service_client = api.ServiceAPIClient()
        return service_client.update_ticket(
            self.id, self.closed_flag, self.priority, self.status
        )

    def close(self, *args, **kwargs):
        """
        Set the ticket to a closed status for the board.
        """
        logger.info('Closing ticket %s' % self.id)
        closed_status = self.board.get_closed_status()
        if closed_status is None:
            raise InvalidStatusError(
                "There are no closed statuses on this ticket's ConnectWise "
                "board ({}). Its status has not been changed.".format(
                    self.board
                )
            )

        self.status = closed_status
        self.closed_flag = True
        return self.save(*args, **kwargs)

    def calculate_sla_expiry(self):
        # We can't guarantee that entered_date_utc won't be null.
        # In the case that it is null, reset the date fields to prevent
        # incorrect SLA calculations.
        if not self.entered_date_utc:
            self.sla_expire_date = None
            self.do_not_escalate_date = None
            self.sla_stage = None
            self.date_resplan_utc = None
            self.date_responded_utc = None
            return

        if not self.status:
            logger.error(
                'Ticket {}-{}, does not have a status set. '
                'Skipping SLA calculation.'.format(self.id, self.summary)
            )
            return

        if not self.sla:
            return

        # SLAP might exist, which may alter the SLA target time
        sla_priority = SlaPriority.objects.filter(
                                                  sla=self.sla,
                                                  priority=self.priority
                                                  ).first()
        if sla_priority:
            sla = sla_priority
        else:
            sla = self.sla

        new_stage = self.STAGE_RANK.get(
            self.status.get_status_rank()
        )

        calendar = self.sla.get_calendar(self.company)

        if not calendar:
            logger.info(
                'No calendar found for SLA {} on ticket {}'.format(
                    sla.id, self.id
                )
            )
            return

        self.change_sla_state(new_stage, calendar, sla)

    def change_sla_state(self, new_stage, calendar, sla):
        valid_stage = self.sla_state.get_valid_next_state(new_stage) \
            if self.sla_state else new_stage

        if valid_stage:
            new_state = self.state_manager.get(valid_stage)(self)

            self.sla_state.leave(calendar, sla) if self.sla_state else None
            self.sla_state = new_state
            self.sla_state.enter(valid_stage, calendar, sla)


class ServiceNote(TimeStampedModel):

    created_by = models.TextField(blank=True, null=True, max_length=250)
    date_created = models.DateTimeField(blank=True, null=True)
    detail_description_flag = models.BooleanField(blank=True)
    external_flag = models.BooleanField(blank=True)
    internal_analysis_flag = models.BooleanField(blank=True)
    internal_flag = models.BooleanField(blank=True)
    resolution_flag = models.BooleanField(blank=True)
    text = models.TextField(blank=True, null=True, max_length=2000)

    ticket = models.ForeignKey('Ticket', on_delete=models.CASCADE)
    member = models.ForeignKey(
        'Member', blank=True, null=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ('-date_created', 'id')
        verbose_name_plural = 'Notes'

    def __str__(self):
        return 'Ticket {} note: {}'.format(self.ticket, str(self.date_created))


class Sla(TimeStampedModel, SlaGoalsMixin):

    BASED_ON = (
        ('MyCalendar', "My Company Calendar"),
        ('Customer', "Customer's Calendar"),
        ('AllHours', "24 Hours"),
        ('Custom', "Custom Calendar")
    )

    name = models.TextField(max_length=250)
    default_flag = models.BooleanField(default=False)
    respond_hours = models.BigIntegerField()
    plan_within = models.BigIntegerField()
    resolution_hours = models.BigIntegerField()
    based_on = models.CharField(max_length=50, choices=BASED_ON,
                                default='MyCalendar')

    calendar = models.ForeignKey(
        'Calendar',
        blank=True,
        null=True,
        on_delete=models.SET_NULL
        )

    class Meta:
        verbose_name_plural = 'SLAs'

    def __str__(self):
        return self.name

    def get_calendar(self, company):
        try:
            if self.calendar:
                return self.calendar
            elif self.based_on == 'Customer' and company:
                return Company.objects.get(id=company.id).calendar
            elif self.based_on == 'MyCalendar':
                # Using get instead of first so it will throw an exception
                return MyCompanyOther.objects.get().default_calendar
            else:
                # Maybe based_on was Customer but company was None
                return None
        except ObjectDoesNotExist:
            return None


class SlaPriority(TimeStampedModel, SlaGoalsMixin):

    sla = models.ForeignKey(
        'Sla',
        on_delete=models.CASCADE
        )
    priority = models.ForeignKey(
        'TicketPriority',
        on_delete=models.CASCADE
        )
    respond_hours = models.FloatField()
    plan_within = models.FloatField()
    resolution_hours = models.FloatField()

    class Meta:
        verbose_name_plural = 'SLA Priorities'

    def __str__(self):
        return 'priority: {}, on SLA:{}'.format(
            str(self.priority), self.sla.id)


class OpportunityNote(TimeStampedModel):

    text = models.TextField(blank=True, null=True, max_length=2000)
    date_created = models.DateTimeField(blank=True, null=True)
    opportunity = models.ForeignKey('Opportunity', on_delete=models.CASCADE)

    class Meta:
        ordering = ('-date_created', 'id', )
        verbose_name_plural = 'Opportunity notes'

    def __str__(self):
        return 'id: {}, on Opportunity id:{}'.format(
            str(self.id), self.opportunity.id)


class Activity(TimeStampedModel):
    name = models.CharField(max_length=250)
    notes = models.TextField(blank=True, null=True, max_length=2000)
    date_start = models.DateTimeField(blank=True, null=True)
    date_end = models.DateTimeField(blank=True, null=True)

    assign_to = models.ForeignKey('Member', on_delete=models.CASCADE)
    opportunity = models.ForeignKey(
        'Opportunity', blank=True, null=True, on_delete=models.CASCADE)
    ticket = models.ForeignKey(
        'Ticket', blank=True, null=True, on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = 'activities'
        # ordering = ('opportunity', 'ticket')

    def __str__(self):
        return self.get_identifier() or ''

    def get_identifier(self):
        return self.name


class SalesProbability(TimeStampedModel):
    probability = models.IntegerField()

    class Meta:
        verbose_name_plural = 'Sales probabilities'
        ordering = ('probability', )

    def __str__(self):
        return 'Probability {}'.format(self.probability)


class SLAMachineState(object):
    valid_next_states = set()

    def __init__(self, ticket):
        self.ticket = ticket

    def enter(self, new_stage, calendar, sla):
        logger.debug('Entering SLA State: {}'.format(self))
        sla_hours = sla.get_stage_hours(new_stage)
        calendar.next_phase_expiry(sla_hours, self.ticket)
        self.ticket.sla_stage = new_stage

    def leave(self, *args):
        logger.debug('Leaving SLA State: {}'.format(self))

    def get_valid_next_state(self, new_state):
        if new_state in self.valid_next_states:
            return new_state


class EscalateState(SLAMachineState):
    valid_next_states = {Ticket.WAITING}


class Respond(EscalateState):
    sla_stage = Ticket.RESPOND

    def __init__(self, ticket):
        super().__init__(ticket)
        self.valid_next_states = self.valid_next_states.union({
                                  Ticket.PLAN,
                                  Ticket.RESOLVE,
                                  Ticket.RESOLVED
                             })


class Plan(EscalateState):
    sla_stage = Ticket.PLAN

    def __init__(self, ticket):
        super().__init__(ticket)
        self.valid_next_states = self.valid_next_states.union({
                                  Ticket.RESOLVE,
                                  Ticket.RESOLVED
                             })


class Resolve(EscalateState):
    sla_stage = Ticket.RESOLVE

    def __init__(self, ticket):
        super().__init__(ticket)
        self.valid_next_states = \
            self.valid_next_states.union({Ticket.RESOLVED})


class Resolved(EscalateState):
    sla_stage = Ticket.RESOLVED

    def __init__(self, ticket):
        super().__init__(ticket)
        self.valid_next_states = self.valid_next_states.union({Ticket.RESOLVE})

    def enter(self, *args):
        self.ticket.sla_expire_date = None
        self.ticket.sla_stage = self.sla_stage

    def get_valid_next_state(self, new_state):
        if new_state == Ticket.WAITING:
            return new_state
        elif new_state != self.sla_stage:
            return Ticket.RESOLVE


class Waiting(SLAMachineState):
    sla_stage = Ticket.WAITING

    def enter(self, *args):
        # Save time entered a non-escalate state to calculate how many minutes
        # it has been waiting if it is ever returned to a regular state
        self.ticket.sla_expire_date = None
        self.ticket.do_not_escalate_date = timezone.now()
        self.ticket.sla_stage = self.sla_stage

    def leave(self, calendar, sla):
        # Get the minutes ticket has been in a non-escalate state,
        # change the state to the desired stage, or the lowest stage allowed,
        # add the minutes spent in waiting to the tickets minutes_waiting field
        # and then recalculate the new stage
        if self.ticket.do_not_escalate_date:
            self.ticket.minutes_waiting += calendar.get_sla_time(
                self.ticket.do_not_escalate_date.astimezone(tz=None),
                timezone.now().astimezone(tz=None)
                )
        self.ticket.do_not_escalate_date = None

    def get_valid_next_state(self, new_state):
        if new_state != Ticket.WAITING:
            return self._lowest_possible_stage(new_state)

    def _lowest_possible_stage(self, stage):
        # Returns the lowest stage a ticket is allowed to go, given the input
        # stage.
        if stage == Ticket.RESOLVED or stage == Ticket.RESOLVE:
            return stage
        elif stage == Ticket.PLAN:
            if self.ticket.date_resplan_utc:
                return Ticket.RESOLVE
            else:
                return stage
        elif stage == Ticket.RESPOND:
            if self.ticket.date_resplan_utc:
                return Ticket.RESOLVE
            elif self.ticket.date_responded_utc:
                return Ticket.PLAN
            else:
                return stage
        else:
            logger.warning('Exiting stage with unknown type')
            return stage


class StateMachineManager(object):
    SLA_STATE = {
        Ticket.RESPOND: Respond,
        Ticket.PLAN: Plan,
        Ticket.RESOLVE: Resolve,
        Ticket.RESOLVED: Resolved,
        Ticket.WAITING: Waiting,
    }

    @classmethod
    def get(cls, state):
        return cls.SLA_STATE.get(state)


class Type(TimeStampedModel):
    name = models.CharField(max_length=50)
    board = models.ForeignKey('ConnectWiseBoard', on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Type'
        verbose_name_plural = 'Types'

    def __str__(self):
        return self.name


class SubType(TimeStampedModel):
    name = models.CharField(max_length=50)
    board = models.ForeignKey('ConnectWiseBoard', on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Subtype'
        verbose_name_plural = 'Subtypes'

    def __str__(self):
        return self.name


class Item(TimeStampedModel):
    name = models.CharField(max_length=50)
    board = models.ForeignKey('ConnectWiseBoard', on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Item'
        verbose_name_plural = 'Items'

    def __str__(self):
        return self.name
