import re
import logging
import urllib
import datetime
from django.conf import settings
from django.utils import timezone
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from django.core.exceptions import ObjectDoesNotExist
from model_utils import FieldTracker
from copy import deepcopy

from . import api

logger = logging.getLogger(__name__)


PRIORITY_RE = re.compile(r'^Priority ([\d]+)')

BILL_TYPES = (
        ('Billable', "Billable"),
        ('DoNotBill', "Do Not Bill"),
        ('NoCharge', "No Charge"),
    )


class UpdateConnectWiseMixin:

    def save(self, *args, **kwargs):
        """
        Save the object.
        If update_cw as a kwarg is True, then update ConnectWise with changes.
        """
        update_cw = kwargs.pop('update_cw', False)
        public_key = kwargs.pop('api_public_key', None)
        private_key = kwargs.pop('api_private_key', None)
        changed_fields = kwargs.pop('changed_fields', None)

        if update_cw and changed_fields:
            self.update_cw(
                api_public_key=public_key,
                api_private_key=private_key,
                changed_fields=changed_fields
            )

        # Ensure save is not run before update_cw returns successfully
        super().save(**kwargs)

    def update_cw(self, **kwargs):
        """
        Send ticket updates to ConnectWise. Accepts a changed_fields
        argument which is a list of fields that have been changed and
        should be updated in CW.
        """
        api_class = self.api_class

        api_client = api_class(
            api_public_key=kwargs.get('api_public_key'),
            api_private_key=kwargs.get('api_private_key')
        )

        changed_fields = kwargs.get('changed_fields')
        updated_objects = self.get_changed_values(changed_fields)

        return self._update_cw(api_client, updated_objects)

    def get_changed_values(self, changed_field_keys):
        # Prepare the updated fields to be sent to CW. At this point, any
        # updated fields have been set on the object, but not in local DB yet.
        updated_objects = {}
        if changed_field_keys:
            for field in changed_field_keys:
                field = field.replace('_id', '')
                updated_objects[field] = getattr(self, field)

        return updated_objects


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
    synchronizer_class = models.CharField(max_length=100, blank=True,
                                          null=True)
    added = models.PositiveIntegerField(null=True)
    updated = models.PositiveIntegerField(null=True)
    deleted = models.PositiveIntegerField(null=True)
    skipped = models.PositiveIntegerField(null=True)
    success = models.BooleanField(null=True)
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
    work_role = models.ForeignKey(
        'WorkRole',
        blank=True,
        null=True,
        on_delete=models.SET_NULL
    )
    work_type = models.ForeignKey(
        'WorkType',
        blank=True,
        null=True,
        on_delete=models.SET_NULL
    )
    bill_time = models.CharField(
        max_length=50,
        choices=BILL_TYPES,
        blank=True, null=True
    )
    project_flag = models.BooleanField(default=False)

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
            # Using first this time because there could be many and we
            # still don't know which one it could be, or just get None.
            closed_status = self.board_statuses.filter(
                name__iregex=r'^([[:space:]]|[[:punct:]])*Closed'
                             r'([[:space:]]|[[:punct:]])*$',
                closed_status=True,
            ).first()

            if not closed_status:
                # There's nothing called "Closed", or "Closed" surrounded by
                # special charaters.
                # filter...first returns None if nothing is found again.
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
    time_entry_not_allowed = models.BooleanField(null=True)
    board = models.ForeignKey(
        'ConnectWiseBoard', blank=True, null=True, on_delete=models.SET_NULL)
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
        ('C', 'StreamlineIT license'),
        ('X', 'Subcontractor license'),
    )
    identifier = models.CharField(  # This is the CW username
        max_length=15, blank=False, unique=True
    )
    first_name = models.CharField(max_length=30, blank=False)
    last_name = models.CharField(max_length=30, blank=False, null=True)
    office_email = models.EmailField(null=True, blank=True, max_length=250)
    inactive = models.BooleanField(default=False)
    avatar = models.CharField(
        null=True, blank=True, max_length=250,
        verbose_name=_('Member Avatar'), help_text=_('Member Avatar')
    )
    license_class = models.CharField(
        blank=True, null=True, max_length=20,
        choices=LICENSE_CLASSES, db_index=True
    )
    work_type = models.ForeignKey(
        'WorkType', null=True, on_delete=models.SET_NULL)
    work_role = models.ForeignKey(
        'WorkRole', null=True, on_delete=models.SET_NULL)

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
    name = models.CharField(blank=True, null=True, max_length=250,
                            db_index=True)
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
    company_types = models.ManyToManyField('CompanyType')
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
        return self.name or ''

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


class Contact(models.Model):

    def __str__(self):
        return '{} {}'.format(self.first_name,
                              self.last_name if self.last_name else '')

    first_name = models.CharField(blank=True, null=True, max_length=200,
                                  db_index=True)
    last_name = models.CharField(blank=True, null=True, max_length=200,
                                 db_index=True)
    title = models.CharField(blank=True, null=True, max_length=200)
    company = models.ForeignKey(
        'Company', null=True, on_delete=models.CASCADE)

    class Meta:
        ordering = ('first_name', 'last_name')

    @property
    def default_email_address(self):
        return self.contactcommunication_set.filter(
            default_flag=True, type_id__email_flag=True).first()

    @property
    def default_phone_number(self):
        return self.contactcommunication_set.filter(
            default_flag=True, type_id__phone_flag=True).first()

    @property
    def default_phone_ext(self):
        phone = self.contactcommunication_set.filter(
            default_flag=True, type_id__phone_flag=True).first()
        return phone.extension if phone else None

    @property
    def default_fax_number(self):
        return self.contactcommunication_set.filter(
            default_flag=True, type_id__fax_flag=True).first()


class ContactCommunication(models.Model):
    contact = models.ForeignKey(
        'Contact', null=True, on_delete=models.CASCADE)
    value = models.CharField(max_length=250)
    extension = models.CharField(blank=True, null=True, max_length=15)
    default_flag = models.BooleanField(blank=True, null=True)
    type = models.ForeignKey(
        'CommunicationType', null=True, on_delete=models.SET_NULL)

    def __str__(self):
        # Do not change this __str__ definition without good reason,
        # email templates rely on it being the value.
        return self.value


class CommunicationType(models.Model):
    description = models.CharField(blank=False, null=False, max_length=250)
    phone_flag = models.BooleanField(default=False)
    fax_flag = models.BooleanField(default=False)
    email_flag = models.BooleanField(default=False)
    default_flag = models.BooleanField(default=False)


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
    date_start = models.DateTimeField(blank=True, null=True)
    date_end = models.DateTimeField(blank=True, null=True)
    done_flag = models.BooleanField(default=False)

    ticket_object = models.ForeignKey(
        'Ticket',
        blank=True,
        null=True,
        on_delete=models.SET_NULL
    )
    activity_object = models.ForeignKey(
        'Activity',
        blank=True,
        null=True,
        on_delete=models.SET_NULL
    )
    member = models.ForeignKey(
        'Member', blank=True, null=True, on_delete=models.SET_NULL)
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

    def delete_entry(self, **kwargs):
        """
        Send Delete request to ConnectWise for this entry
        """
        schedule_client = api.ScheduleAPIClient(
            api_public_key=kwargs.get('api_public_key'),
            api_private_key=kwargs.get('api_private_key')
        )
        return schedule_client.delete_schedule_entry(self.id)


class Territory(models.Model):
    name = models.CharField(max_length=250, blank=True, null=True)

    class Meta:
        verbose_name_plural = 'Territories'
        ordering = ('name', )

    def __str__(self):
        return self.name


class UpdateRecordMixin:

    def save(self, *args, **kwargs):
        update_cw = kwargs.pop('update_cw', False)
        public_key = kwargs.pop('api_public_key', None)
        private_key = kwargs.pop('api_private_key', None)

        if update_cw:
            self.update_cw(
                api_public_key=public_key,
                api_private_key=private_key,
            )
        super().save(**kwargs)


class TimeEntry(UpdateRecordMixin, models.Model):
    CHARGE_TYPES = (
        ('ServiceTicket', "Service Ticket"),
        ('ProjectTicket', "Project Ticket"),
        ('ChargeCode', "Charge Code"),
        ('Activity', "Activity")
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
    notes = models.TextField(blank=True, null=True, max_length=50000)
    time_start = models.DateTimeField(blank=True, null=True)
    time_end = models.DateTimeField(blank=True, null=True)

    detail_description_flag = models.BooleanField(default=False)
    internal_analysis_flag = models.BooleanField(default=False)
    resolution_flag = models.BooleanField(default=False)

    email_resource_flag = models.BooleanField(default=False)
    email_contact_flag = models.BooleanField(default=False)
    email_cc_flag = models.BooleanField(default=False)
    email_cc = models.CharField(blank=True, null=True, max_length=1000)

    charge_to_id = models.ForeignKey(
        'Ticket', blank=True, null=True, on_delete=models.CASCADE)
    company = models.ForeignKey(
        'Company', blank=True, null=True, on_delete=models.SET_NULL)
    member = models.ForeignKey(
        'Member', blank=True, null=True, on_delete=models.CASCADE)
    work_type = models.ForeignKey(
        'WorkType', blank=True, null=True, on_delete=models.SET_NULL)
    agreement = models.ForeignKey(
        'Agreement', blank=True, null=True, on_delete=models.SET_NULL)

    def get_entered_time(self):
        if self.time_end:
            entered_time = self.time_end
        elif self.actual_hours:
            # timedelta does not like decimals
            minutes = int(self.actual_hours * 60)
            entered_time = self.time_start + timezone.timedelta(
                minutes=minutes)
        else:
            entered_time = self.time_start

        return entered_time

    def get_time_start(self):
        time_start = self.time_start

        # CW allows creating a time entry with actual hours set
        # but no start or end time. In this case, the API returns time_start
        # with the date and time as UTC midnight and time_end as null.
        # Use a naive date instead to prevent conversion problems in the
        # templates.
        if self.time_start and not self.time_end:
            time_start = time_start.date()

        return time_start

    @property
    def note(self):
        return self.notes

    def update_cw(self, **kwargs):

        api_client = api.TimeAPIClient(
            api_public_key=kwargs.get('api_public_key'),
            api_private_key=kwargs.get('api_private_key')
        )
        return api_client.update_time_entry(self)


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


class ProjectType(TimeStampedModel):
    name = models.CharField(max_length=30)
    default_flag = models.BooleanField(default=False)
    inactive_flag = models.BooleanField(default=False)

    class Meta:
        ordering = ('name', )
        verbose_name_plural = 'Project types'

    def __str__(self):
        return self.name


class ProjectPhase(TimeStampedModel):
    description = models.CharField(max_length=100)
    scheduled_start = models.DateField(blank=True, null=True)
    scheduled_end = models.DateField(blank=True, null=True)
    actual_start = models.DateField(blank=True, null=True)
    actual_end = models.DateField(blank=True, null=True)

    bill_time = models.CharField(
        max_length=50, choices=BILL_TYPES, blank=True, null=True)
    notes = models.TextField(null=True, blank=False)
    scheduled_hours = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=9)
    actual_hours = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=9)
    budget_hours = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=9)
    wbs_code = models.CharField(max_length=50, blank=True, null=True)

    project = models.ForeignKey(
        'Project', blank=True, null=True, on_delete=models.SET_NULL
    )
    board = models.ForeignKey(
        'ConnectwiseBoard', blank=True, null=True, on_delete=models.SET_NULL
    )

    class Meta:
        verbose_name_plural = 'Project phases'

    def __str__(self):
        return self.description


class ProjectTeamMember(TimeStampedModel):
    start_date = models.DateTimeField(blank=True, null=True)
    end_date = models.DateTimeField(blank=True, null=True)

    project = models.ForeignKey(
        'Project', null=True, on_delete=models.SET_NULL
    )
    member = models.ForeignKey(
        'Member', null=True, on_delete=models.SET_NULL
    )
    work_role = models.ForeignKey(
        'WorkRole', null=True, on_delete=models.SET_NULL
    )

    def __str__(self):
        return '{}/{}'.format(self.id, self.member)


class AvailableProjectManager(models.Manager):
    """
    Return only projects whose status closed field is False.
    """
    def get_queryset(self):
        return super().get_queryset().filter(
            status__closed_flag=False,
        )


class Project(UpdateConnectWiseMixin, TimeStampedModel):
    name = models.CharField(max_length=200)
    actual_hours = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=9)
    budget_hours = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=12)
    scheduled_hours = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=9)
    actual_start = models.DateField(blank=True, null=True)
    actual_end = models.DateField(blank=True, null=True)
    estimated_start = models.DateField(blank=True, null=True)
    estimated_end = models.DateField(blank=True, null=True)
    percent_complete = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=3)
    scheduled_start = models.DateField(blank=True, null=True)
    scheduled_end = models.DateField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    udf = models.JSONField(blank=True, null=True)

    board = models.ForeignKey(
        'ConnectWiseBoard',
        blank=True,
        null=True,
        on_delete=models.SET_NULL
    )
    company = models.ForeignKey(
        'Company', on_delete=models.SET_NULL, blank=True, null=True
    )
    contact = models.ForeignKey('Contact', blank=True, null=True,
                                on_delete=models.SET_NULL)
    status = models.ForeignKey(
        'ProjectStatus', blank=True, null=True, on_delete=models.SET_NULL)
    manager = models.ForeignKey(
        'Member',
        blank=True,
        null=True,
        related_name='project_manager',
        on_delete=models.SET_NULL
    )
    type = models.ForeignKey(
        'ProjectType',
        blank=True,
        null=True,
        on_delete=models.SET_NULL
    )
    team_members = models.ManyToManyField(
        'Member', through='ProjectTeamMember',
    )

    objects = models.Manager()
    available_objects = AvailableProjectManager()

    EDITABLE_FIELDS = {
        'name': 'name',
        'status': 'status',
        'type': 'type',
        'estimated_start': 'estimatedStart',
        'estimated_end': 'estimatedEnd',
        'manager': 'manager',
        'percent_complete': 'percentComplete',
        'description': 'description',
        'contact': 'contact',
    }

    class Meta:
        ordering = ('name', )

    def __str__(self):
        return self.name or ''

    @property
    def api_class(self):
        return api.ProjectAPIClient

    def _update_cw(self, api_client, updated_objects):
        return api_client.update_project(self, updated_objects)

    def get_connectwise_url(self):
        params = dict(
            recordType='ProjectHeaderFV',
            recid=self.id,
            companyName=settings.CONNECTWISE_CREDENTIALS['company_id']
        )
        return '{}/{}?{}'.format(
            settings.CONNECTWISE_SERVER_URL,
            settings.CONNECTWISE_TICKET_PATH,
            urllib.parse.urlencode(params)
        )

    def percentage_complete(self):
        percent_value = self.percent_complete if self.percent_complete else 0

        return self.calculate_percentage(percent_value)

    def calculate_percentage(self, value):
        return round(value * 100)

    def get_changed_values(self, changed_field_keys):
        updated_objects = super().get_changed_values(changed_field_keys)

        percent_complete = updated_objects.get('percent_complete')
        if percent_complete:
            # CW accepts percentComplete as the percentage value, not as
            # the decimal value.
            # For example, the API returns "percentComplete": 0.2500, when
            # we submit "percentComplete": 25.
            updated_objects['percent_complete'] = \
                self.calculate_percentage(percent_complete)

        return updated_objects


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


class Opportunity(UpdateConnectWiseMixin, TimeStampedModel):
    business_unit_id = models.IntegerField(null=True)
    closed_date = models.DateTimeField(blank=True, null=True)
    customer_po = models.CharField(max_length=100, blank=True, null=True)
    date_became_lead = models.DateTimeField(blank=True, null=True)
    expected_close_date = models.DateField()
    location_id = models.IntegerField()
    name = models.CharField(max_length=100, db_index=True)
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
    contact = models.ForeignKey('Contact', blank=True, null=True,
                                on_delete=models.SET_NULL)
    primary_sales_rep = models.ForeignKey('Member',
                                          blank=True, null=True,
                                          related_name='opportunity_primary',
                                          on_delete=models.SET_NULL)
    priority = models.ForeignKey('OpportunityPriority',
                                 on_delete=models.SET_NULL, null=True)
    stage = models.ForeignKey('OpportunityStage', blank=True, null=True,
                              on_delete=models.SET_NULL)
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
    udf = models.JSONField(blank=True, null=True)

    EDITABLE_FIELDS = {
        'name': 'name',
        'stage': 'stage',
        'notes': 'notes',
        'contact': 'contact',
        'expected_close_date': 'expectedCloseDate',
        'opportunity_type': 'type',
        'status': 'status',
        'source': 'source',
        'primary_sales_rep': 'primarySalesRep',
        'secondary_sales_rep': 'secondarySalesRep',
        'location_id': 'locationId',
    }

    class Meta:
        ordering = ('name', )
        verbose_name_plural = 'Opportunities'

    def __str__(self):
        return self.name

    @property
    def api_class(self):
        return api.SalesAPIClient

    def _update_cw(self, api_client, updated_objects):
        return api_client.update_opportunity(self, updated_objects)

    def get_descriptor(self):
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


class Ticket(UpdateConnectWiseMixin, TimeStampedModel):
    SCHEDULE_ENTRY_TYPE = "S"

    PROJECT_TICKET = 'ProjectTicket'
    PROJECT_ISSUE = 'ProjectIssue'
    SERVICE_TICKET = 'ServiceTicket'

    RECORD_TYPES = (
        (SERVICE_TICKET, "Service Ticket"),
        (PROJECT_TICKET, "Project Ticket"),
        (PROJECT_ISSUE, "Project Issue"),
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
    TICKET = 'Ticket'
    PHASE = 'Phase'
    PREDECESSOR_TYPES = (
        (TICKET, 'Ticket'),
        (PHASE, 'Phase')
    )

    VALID_UPDATE_FIELDS = {
        'summary': 'summary',
        'required_date_utc': 'requiredDate',
        'budget_hours': 'budgetHours',
        'closed_flag': 'closedFlag',
        'owner': 'owner',
        'type': 'type',
        'sub_type': 'subType',
        'sub_type_item': 'item',
        'agreement': 'agreement',
        'status': 'status',
        'priority': 'priority',
        'board': 'board',
    }

    SERVICE_EDITABLE_FIELDS = VALID_UPDATE_FIELDS
    PROJECT_EDITABLE_FIELDS = deepcopy(VALID_UPDATE_FIELDS)
    PROJECT_EDITABLE_FIELDS.update({
        'project': 'project',
        'phase': 'phase'
    })
    SERVICE_EDITABLE_FIELDS.update({
        'company': 'company',
        'contact': 'contact',
    })
    EDITABLE_FIELDS = {
        PROJECT_TICKET: PROJECT_EDITABLE_FIELDS,
        PROJECT_ISSUE: PROJECT_EDITABLE_FIELDS,
        SERVICE_TICKET: SERVICE_EDITABLE_FIELDS,
    }

    actual_hours = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=9)
    approved = models.BooleanField(null=True)
    budget_hours = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=12)
    closed_by = models.CharField(blank=True, null=True, max_length=250)
    closed_date_utc = models.DateTimeField(blank=True, null=True)
    closed_flag = models.BooleanField(null=True)
    customer_updated = models.BooleanField(default=False)
    date_resolved_utc = models.DateTimeField(blank=True, null=True)
    date_resplan_utc = models.DateTimeField(blank=True, null=True)
    date_responded_utc = models.DateTimeField(blank=True, null=True)
    entered_date_utc = models.DateTimeField(blank=True, null=True)
    has_child_ticket = models.BooleanField(null=True)
    impact = models.CharField(blank=True, null=True, max_length=250)
    is_in_sla = models.BooleanField(null=True)
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
    summary = models.CharField(blank=True, null=True, db_index=True,
                               max_length=250)
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
    automatic_email_cc = models.CharField(blank=True,
                                          null=True,
                                          max_length=1000)
    automatic_email_contact_flag = models.BooleanField(default=False)
    automatic_email_resource_flag = models.BooleanField(default=False)

    predecessor_type = models.CharField(blank=True, null=True, max_length=10,
                                        choices=PREDECESSOR_TYPES)
    lag_days = models.IntegerField(blank=True, null=True)
    lag_non_working_days_flag = models.BooleanField(default=False)
    estimated_start_date = models.DateTimeField(blank=True, null=True)
    wbs_code = models.CharField(blank=True, null=True, max_length=50)
    udf = models.JSONField(blank=True, null=True)
    tasks_completed = models.PositiveSmallIntegerField(blank=True, null=True)
    tasks_total = models.PositiveSmallIntegerField(blank=True, null=True)

    ticket_predecessor = models.ForeignKey(
        'self', blank=True, null=True, on_delete=models.SET_NULL
    )
    phase_predecessor = models.ForeignKey(
        'ProjectPhase', blank=True, null=True, on_delete=models.SET_NULL
    )
    board = models.ForeignKey(
        'ConnectwiseBoard', blank=True, null=True, on_delete=models.SET_NULL)
    company = models.ForeignKey(
        'Company', blank=True, null=True, related_name='company_tickets',
        on_delete=models.SET_NULL)
    contact = models.ForeignKey('Contact', blank=True, null=True,
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
        on_delete=models.SET_NULL)
    phase = models.ForeignKey(
        'ProjectPhase', blank=True, null=True, related_name='phase_tickets',
        on_delete=models.SET_NULL)
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
    agreement = models.ForeignKey(
        'Agreement', blank=True, null=True, related_name='agreement_tickets',
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

    @property
    def api_class(self):
        if self.record_type in [self.PROJECT_TICKET, self.PROJECT_ISSUE]:
            api_class = api.ProjectAPIClient
        else:
            api_class = api.ServiceAPIClient

        return api_class

    def _update_cw(self, api_client, updated_objects):
        return api_client.update_ticket(self, updated_objects)

    def get_descriptor(self):
        return self.summary

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
        self._warn_invalid_status()
        super().save(**kwargs)

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

        kwargs['changed_fields'] = ['status', 'closed_flag']

        return self.save(*args, **kwargs)

    def calculate_sla_expiry(self, priority_change=None):
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

        if priority_change:
            # When only the SLA priority has changed, we don't need to
            # change the state, just re-calculate the next SLA expiry date.
            sla_hours = sla.get_stage_hours(new_stage)
            if sla_hours:
                calendar.next_phase_expiry(sla_hours, self)
        else:
            self.change_sla_state(new_stage, calendar, sla)

    def change_sla_state(self, new_stage, calendar, sla):
        valid_stage = self.sla_state.get_valid_next_state(new_stage) \
            if self.sla_state else new_stage

        if valid_stage:
            new_state = self.state_manager.get(valid_stage)(self)

            self.sla_state.leave(calendar, sla) if self.sla_state else None
            self.sla_state = new_state
            self.sla_state.enter(valid_stage, calendar, sla)


class ServiceNote(UpdateRecordMixin, TimeStampedModel):

    created_by = models.TextField(blank=True, null=True, max_length=250)
    date_created = models.DateTimeField(blank=True, null=True)
    detail_description_flag = models.BooleanField(blank=True)
    external_flag = models.BooleanField(blank=True)
    internal_analysis_flag = models.BooleanField(blank=True)
    internal_flag = models.BooleanField(blank=True)
    resolution_flag = models.BooleanField(blank=True)
    text = models.TextField(blank=True, null=True, max_length=4000)

    ticket = models.ForeignKey('Ticket', on_delete=models.CASCADE)
    member = models.ForeignKey(
        'Member', blank=True, null=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ('-date_created', 'id')
        verbose_name_plural = 'Notes'

    def __str__(self):
        return 'Ticket {} note: {}'.format(self.ticket, str(self.date_created))

    def get_entered_time(self):
        return self.date_created

    @property
    def note(self):
        return self.text

    def update_cw(self, **kwargs):
        api_class = self.ticket.api_class

        api_client = api_class(
            api_public_key=kwargs.get('api_public_key'),
            api_private_key=kwargs.get('api_private_key')
        )
        return api_client.update_note(self)


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


class ActivityStatus(TimeStampedModel):
    name = models.CharField(max_length=50)
    default_flag = models.BooleanField(default=False)
    inactive_flag = models.BooleanField(default=False)
    spawn_followup_flag = models.BooleanField(default=False)
    closed_flag = models.BooleanField(default=False)

    class Meta:
        ordering = ('name', )
        verbose_name_plural = 'activity statuses'

    def __str__(self):
        return self.name


class ActivityType(TimeStampedModel):
    name = models.CharField(max_length=50)
    points = models.IntegerField()
    default_flag = models.BooleanField(default=False)
    inactive_flag = models.BooleanField(default=False)
    email_flag = models.BooleanField(default=False)
    memo_flag = models.BooleanField(default=False)
    history_flag = models.BooleanField(default=False)

    class Meta:
        ordering = ('name', )

    def __str__(self):
        return self.name


class Activity(UpdateConnectWiseMixin, TimeStampedModel):
    name = models.CharField(max_length=250)
    notes = models.TextField(blank=True, null=True, max_length=2000)
    date_start = models.DateTimeField(blank=True, null=True)
    date_end = models.DateTimeField(blank=True, null=True)

    assign_to = models.ForeignKey('Member', on_delete=models.CASCADE)
    opportunity = models.ForeignKey(
        'Opportunity', blank=True, null=True, on_delete=models.CASCADE)
    ticket = models.ForeignKey(
        'Ticket', blank=True, null=True, on_delete=models.CASCADE)
    status = models.ForeignKey(
        'ActivityStatus', blank=True, null=True, on_delete=models.SET_NULL)
    type = models.ForeignKey(
        'ActivityType', blank=True, null=True, on_delete=models.SET_NULL)
    company = models.ForeignKey(
        'Company', blank=True, null=True, on_delete=models.SET_NULL)
    contact = models.ForeignKey('Contact', blank=True, null=True,
                                on_delete=models.SET_NULL)
    agreement = models.ForeignKey(
        'Agreement', blank=True, null=True, on_delete=models.SET_NULL)
    udf = models.JSONField(blank=True, null=True)

    EDITABLE_FIELDS = {
        'name': 'name',
        'status': 'status',
        'notes': 'notes',
        'type': 'type',
        'assign_to': 'assignTo',
        'company': 'company',
        'contact': 'contact',
        'agreement': 'agreement',
        'opportunity': 'opportunity',
        'ticket': 'ticket',
        'date_start': 'dateStart',
        'date_end': 'dateEnd',
    }

    class Meta:
        verbose_name_plural = 'activities'

    def __str__(self):
        return self.name or ''

    @property
    def api_class(self):
        return api.SalesAPIClient

    def _update_cw(self, api_client, updated_objects):
        return api_client.update_activity(self, updated_objects)

    def get_connectwise_url(self):
        params = dict(
            recordType='ActivityFv',
            recid=self.id,
            companyName=settings.CONNECTWISE_CREDENTIALS['company_id']
        )
        return '{}/{}?{}'.format(
            settings.CONNECTWISE_SERVER_URL,
            settings.CONNECTWISE_TICKET_PATH,
            urllib.parse.urlencode(params)
        )


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
    inactive_flag = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Type'
        verbose_name_plural = 'Types'

    def __str__(self):
        return "{} - {}".format(self.name, self.board)


class SubType(TimeStampedModel):
    name = models.CharField(max_length=50)
    board = models.ForeignKey('ConnectWiseBoard', on_delete=models.CASCADE)
    inactive_flag = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Subtype'
        verbose_name_plural = 'Subtypes'

    def __str__(self):
        return self.name


class Item(TimeStampedModel):
    name = models.CharField(max_length=50)
    board = models.ForeignKey('ConnectWiseBoard', on_delete=models.CASCADE)
    inactive_flag = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Item'
        verbose_name_plural = 'Items'

    def __str__(self):
        return self.name


class TypeSubTypeItemAssociation(TimeStampedModel):
    type = models.ForeignKey('Type', blank=True, null=True,
                             related_name='associations',
                             on_delete=models.CASCADE)
    sub_type = models.ForeignKey('SubType', blank=True,
                                 related_name='associations',
                                 null=True, on_delete=models.CASCADE)
    item = models.ForeignKey('Item', blank=True,
                             related_name='associations',
                             null=True, on_delete=models.CASCADE)
    board = models.ForeignKey('ConnectWiseBoard', blank=True,
                              null=True, on_delete=models.CASCADE)


class WorkType(TimeStampedModel):
    name = models.CharField(max_length=50)
    inactive_flag = models.BooleanField(default=False)
    overall_default_flag = models.BooleanField(default=False)
    bill_time = models.CharField(
        max_length=50, choices=BILL_TYPES, blank=True, null=True
    )

    def __str__(self):
        return self.name


class WorkRole(TimeStampedModel):
    name = models.CharField(max_length=50)
    inactive_flag = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class Agreement(TimeStampedModel):
    name = models.CharField(max_length=100)
    agreement_type = models.CharField(max_length=50, null=True)
    agreement_status = models.CharField(max_length=50, blank=True, null=True)
    cancelled_flag = models.BooleanField(default=False)
    bill_time = models.CharField(
        max_length=50, choices=BILL_TYPES, blank=True, null=True
    )
    work_type = models.ForeignKey(
        'WorkType', null=True, on_delete=models.SET_NULL)
    work_role = models.ForeignKey(
        'WorkRole', null=True, on_delete=models.SET_NULL)
    company = models.ForeignKey(
        'Company', null=True, on_delete=models.SET_NULL)

    def __str__(self):
        return '{}/{}'.format(self.agreement_type, self.name)


class BaseUDF(TimeStampedModel):
    caption = models.CharField(max_length=50, blank=True, null=True)
    type = models.CharField(max_length=50, blank=True, null=True)
    entry_method = models.CharField(max_length=50, blank=True, null=True)
    number_of_decimals = \
        models.PositiveSmallIntegerField(blank=True, null=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.caption


class TicketUDF(BaseUDF):
    pass


class ProjectUDF(BaseUDF):
    pass


class ActivityUDF(BaseUDF):
    pass


class OpportunityUDF(BaseUDF):
    pass


class TicketTracker(Ticket):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_ticket'


class ConnectWiseBoardTracker(ConnectWiseBoard):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_connectwiseboard'


class BoardStatusTracker(BoardStatus):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_boardstatus'


class LocationTracker(Location):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_location'


class MemberTracker(Member):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_member'


class CompanyTracker(Company):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_company'


class CompanyStatusTracker(CompanyStatus):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_companystatus'


class CompanyTypeTracker(CompanyType):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_companytype'


class ContactTracker(Contact):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_contact'


class ContactCommunicationTracker(ContactCommunication):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_contactcommunication'


class CommunicationTypeTracker(CommunicationType):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_communicationtype'


class MyCompanyOtherTracker(MyCompanyOther):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_mycompanyother'


class CalendarTracker(Calendar):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_calendar'


class HolidayTracker(Holiday):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_holiday'


class HolidayListTracker(HolidayList):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_holidaylist'


class ScheduleTypeTracker(ScheduleType):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_scheduletype'


class ScheduleStatusTracker(ScheduleStatus):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_schedulestatus'


class ScheduleEntryTracker(ScheduleEntry):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_scheduleentry'


class TerritoryTracker(Territory):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_territory'


class TimeEntryTracker(TimeEntry):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_timeentry'


class TeamTracker(Team):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_team'


class TicketPriorityTracker(TicketPriority):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_ticketpriority'


class ProjectStatusTracker(ProjectStatus):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_projectstatus'


class ProjectTypeTracker(ProjectType):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_projecttype'


class ProjectPhaseTracker(ProjectPhase):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_projectphase'


class ProjectTeamMemberTracker(ProjectTeamMember):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_projectteammember'


class ProjectTracker(Project):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_project'


class OpportunityStageTracker(OpportunityStage):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_opportunitystage'


class OpportunityStatusTracker(OpportunityStatus):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_opportunitystatus'


class OpportunityPriorityTracker(OpportunityPriority):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_opportunitypriority'


class OpportunityTypeTracker(OpportunityType):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_opportunitytype'


class OpportunityTracker(Opportunity):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_opportunity'


class ServiceNoteTracker(ServiceNote):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_servicenote'


class SlaTracker(Sla):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_sla'


class SlaPriorityTracker(SlaPriority):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_slapriority'


class OpportunityNoteTracker(OpportunityNote):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_opportunitynote'


class ActivityStatusTracker(ActivityStatus):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_activitystatus'


class ActivityTypeTracker(ActivityType):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_activitytype'


class ActivityTracker(Activity):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_activity'


class SalesProbabilityTracker(SalesProbability):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_salesprobability'


class TypeTracker(Type):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_type'


class SubTypeTracker(SubType):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_subtype'


class ItemTracker(Item):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_item'


class TypeSubTypeItemAssociationTracker(TypeSubTypeItemAssociation):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_type_subtype_item_association'


class WorkTypeTracker(WorkType):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_worktype'


class WorkRoleTracker(WorkRole):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_workrole'


class AgreementTracker(Agreement):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_agreement'


class TicketUDFTracker(TicketUDF):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_ticketudf'


class ProjectUDFTracker(ProjectUDF):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_projectudf'


class ActivityUDFTracker(ActivityUDF):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_activityudf'


class OpportunityUDFTracker(OpportunityUDF):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_opportunityudf'
