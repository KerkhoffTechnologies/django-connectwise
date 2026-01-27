import datetime
import logging
import re
import urllib

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from model_utils import FieldTracker

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

        Update in this context means to update connectwise with new data,
        updates can be PATCH to update existing records, or POST to
        create new records.
        """
        # TODO remove all update_cw calls and related after synchronizers
        #  handle updates to PSA
        api_class = self.api_class

        api_client = api_class(
            api_public_key=kwargs.get('api_public_key'),
            api_private_key=kwargs.get('api_private_key')
        )

        changed_fields = kwargs.get('changed_fields')
        # TODO improve naming when moved to synchronizer
        updated_objects = self.get_changed_values(changed_fields)

        return self._update_cw(api_client, updated_objects)

    def get_changed_values(self, changed_field_keys):
        # TODO remove this method after synchronizers handle updates to PSA
        # Prepare the updated fields to be sent to CW. At this point, any
        # updated fields have been set on the object, but not in local DB yet.
        updated_objects = {}
        if changed_field_keys:
            for field in changed_field_keys:
                updated_objects[field] = getattr(self, field)

        return updated_objects


class InvalidStatusError(Exception):
    pass


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
    time_entry_discussion_flag = models.BooleanField(default=False)
    time_entry_resolution_flag = models.BooleanField(default=False)
    time_entry_internal_analysis_flag = models.BooleanField(default=False)
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
    title = models.CharField(blank=True, null=True, max_length=250)

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

    def get_connectwise_url(self):
        params = dict(
            recordType='CompanyFV',
            recid=self.id,
            companyName=settings.CONNECTWISE_CREDENTIALS['company_id']
        )
        return '{}/{}?{}'.format(
            settings.CONNECTWISE_SERVER_URL,
            settings.CONNECTWISE_TICKET_PATH,
            urllib.parse.urlencode(params)
        )


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
    default_flag = models.BooleanField(blank=True, null=True)
    service_alert_flag = models.BooleanField(blank=True, null=True)
    service_alert_message = models.TextField(
        blank=True, null=True
    )

    class Meta:
        ordering = ('name', )

    def __str__(self):
        return self.name


class ContactType(models.Model):
    description = models.CharField(max_length=250)
    default_flag = models.BooleanField()
    service_alert_flag = models.BooleanField(
        blank=True, null=True)
    service_alert_message = models.TextField(
        blank=True, null=True
    )

    class Meta:
        ordering = ('description', )

    def __str__(self):
        return self.description


class CompanyNoteType(models.Model):
    name = models.CharField(max_length=50)
    identifier = models.CharField(max_length=50)
    default_flag = models.BooleanField()

    class Meta:
        ordering = ('name', )

    def __str__(self):
        return self.name


class CompanyTeam(models.Model):
    company = models.ForeignKey('Company', blank=True,
                                null=True, on_delete=models.CASCADE)
    team_role = models.ForeignKey('CompanyTeamRole',
                                  blank=True, null=True,
                                  on_delete=models.CASCADE)
    location = models.ForeignKey('Location', blank=True,
                                 null=True, on_delete=models.CASCADE)
    contact = models.ForeignKey('Contact', blank=True,
                                null=True, on_delete=models.CASCADE)
    member = models.ForeignKey('Member', blank=True,
                               null=True, on_delete=models.CASCADE)
    account_manager_flag = models.BooleanField()
    tech_flag = models.BooleanField()
    sales_flag = models.BooleanField()

    class Meta:
        ordering = ('id', )

    def __str__(self):
        return self.company.name


class CompanySite(models.Model):
    name = models.CharField(max_length=255)
    inactive = models.BooleanField(default=False,
                                   null=True)
    company = models.ForeignKey('Company', blank=True,
                                null=True, on_delete=models.CASCADE)

    class Meta:
        ordering = ('id', )

    def __str__(self):
        return self.name


class CompanyTeamRole(models.Model):
    name = models.CharField(max_length=50)
    account_manager_flag = models.BooleanField()
    tech_flag = models.BooleanField()
    sales_flag = models.BooleanField()

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
    type = models.ManyToManyField('ContactType')

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

    def get_connectwise_url(self):
        params = dict(
            recordType='ContactFV',
            recid=self.id,
            companyName=settings.CONNECTWISE_CREDENTIALS['company_id']
        )
        return '{}/{}?{}'.format(
            settings.CONNECTWISE_SERVER_URL,
            settings.CONNECTWISE_TICKET_PATH,
            urllib.parse.urlencode(params)
        )


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

    def __str__(self):
        return self.description


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


class SystemLocation(models.Model):
    name = models.CharField(max_length=250, blank=True, null=True)
    owner_level_id = models.IntegerField(blank=True, null=True)
    reports_to = models.ForeignKey('self', blank=True, null=True,
                                   on_delete=models.SET_NULL)
    location_flag = models.BooleanField(default=False)
    client_flag = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'System Location'
        verbose_name_plural = 'System Locations'
        ordering = ('name', )

    def __str__(self):
        return self.name or ''


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


class NonInternalTimeEntryManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().exclude(internal_analysis_flag=True)


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
    system_location = models.ForeignKey(
        'SystemLocation', blank=True, null=True, on_delete=models.SET_NULL)

    objects = models.Manager()
    non_internal_objects = NonInternalTimeEntryManager()

    @property
    def note(self):
        return self.notes

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

    def get_time_end(self):
        return self.time_end

    def get_time_actual(self):
        return self.actual_hours

    def get_sort_date(self):
        """
        Return the appropriate date field of the given item. Used for sorting
        service notes and time entries together.
        """
        date_field = self.time_end if self.time_end else self.time_start

        return date_field

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
    required_date = models.DateField(blank=True, null=True)

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
    project_role = models.ForeignKey(
        'ProjectRole', null=True, on_delete=models.SET_NULL
    )

    def __str__(self):
        return '{}/{}'.format(self.id, self.member)


class ProjectRole(TimeStampedModel):
    name = models.CharField(max_length=30)
    manager_role_flag = models.BooleanField(default=False)
    default_contact_flag = models.BooleanField(default=False)

    class Meta:
        ordering = ('name', )
        verbose_name_plural = 'Project role'

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
        blank=True, null=True, decimal_places=2, max_digits=5)
    scheduled_start = models.DateField(blank=True, null=True)
    scheduled_end = models.DateField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    udf = models.JSONField(blank=True, null=True)

    ACTUAL_RATES = 'ActualRates'
    FIXED_FEE = 'FixedFee'
    NOT_TO_EXCEED = 'NotToExceed'
    OVERRIDE_RATE = 'OverrideRate'

    BILLING_METHODS = (
        (ACTUAL_RATES, 'Actual Rates'),
        (FIXED_FEE, 'Fixed Fee'),
        (NOT_TO_EXCEED, 'Not To Exceed'),
        (OVERRIDE_RATE, 'Override Rate'),
    )
    billing_method = models.CharField(null=True, blank=True,
                                      choices=BILLING_METHODS, max_length=50)

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

    @staticmethod
    def calculate_percentage(value):
        return round(value * 100)


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


class ConfigurationStatus(TimeStampedModel):
    description = models.CharField(max_length=255)
    closed_flag = models.BooleanField(default=False)
    default_flag = models.BooleanField(default=False)

    class Meta:
        ordering = ['description']
        verbose_name_plural = 'Configuration Statuses'

    def __str__(self):
        return self.description

    @property
    def api_class(self):
        return api.ConfigurationAPIClient


class ConfigurationType(TimeStampedModel):
    name = models.TextField(max_length=250)
    inactive_flag = models.BooleanField(default=False)
    system_flag = models.BooleanField(default=False)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Configuration Types'

    def __str__(self):
        return self.name

    @property
    def api_class(self):
        return api.ConfigurationAPIClient


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

    TICKET = 'Ticket'
    PHASE = 'Phase'
    PREDECESSOR_TYPES = (
        (TICKET, 'Ticket'),
        (PHASE, 'Phase')
    )

    actual_hours = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=9)
    approved = models.BooleanField(null=True)
    budget_hours = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=12)
    closed_by = models.CharField(blank=True, null=True, max_length=1000)
    closed_date_utc = models.DateTimeField(blank=True, null=True)
    closed_flag = models.BooleanField(null=True)
    customer_updated = models.BooleanField(default=False)

    entered_date_utc = models.DateTimeField(blank=True, null=True)
    has_child_ticket = models.BooleanField(null=True)
    impact = models.CharField(blank=True, null=True, max_length=1000)
    is_in_sla = models.BooleanField(null=True)
    last_updated_utc = models.DateTimeField(blank=True, null=True)
    parent_ticket_id = models.IntegerField(blank=True, null=True)
    record_type = models.CharField(blank=True, null=True,
                                   max_length=1000, choices=RECORD_TYPES,
                                   db_index=True)
    required_date_utc = models.DateTimeField(blank=True, null=True)

    sla_expire_date = models.DateTimeField(blank=True, null=True)
    sla_stage = models.CharField(blank=True, null=True,
                                 max_length=1000, choices=SLA_STAGE,
                                 db_index=True)

    resources = models.CharField(blank=True, null=True, max_length=1000)
    severity = models.CharField(blank=True, null=True, max_length=1000)
    site_name = models.CharField(blank=True, null=True, max_length=1000)
    summary = models.CharField(blank=True, null=True, db_index=True,
                               max_length=1000)
    updated_by = models.CharField(blank=True, null=True, max_length=1000)

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
    predecessor_closed_flag = models.BooleanField(default=False)
    lag_days = models.IntegerField(blank=True, null=True)
    lag_non_working_days_flag = models.BooleanField(default=False)
    estimated_start_date = models.DateTimeField(blank=True, null=True)
    wbs_code = models.CharField(blank=True, null=True, max_length=50)
    udf = models.JSONField(blank=True, null=True)
    tasks_completed = models.PositiveSmallIntegerField(blank=True, null=True)
    tasks_total = models.PositiveSmallIntegerField(blank=True, null=True)
    is_issue_flag = models.BooleanField(default=False)
    contact_name = models.CharField(blank=True, null=True, max_length=62)
    contact_phone_number = models.CharField(blank=True,
                                            null=True, max_length=20)
    contact_phone_extension = models.CharField(blank=True,
                                               null=True, max_length=15)
    contact_email_address = models.CharField(blank=True,
                                             null=True, max_length=250)

    # Only used for creation, not synced.
    initial_description = models.CharField(
        blank=True, null=True, max_length=5000)

    ticket_predecessor = models.ForeignKey(
        'self', blank=True, null=True, on_delete=models.SET_NULL,
        related_name="ticket_predecessor_ticket"
    )
    merged_parent = models.ForeignKey(
        'self', blank=True, null=True, on_delete=models.SET_NULL,
        related_name="merged_parent_ticket"
    )
    phase_predecessor = models.ForeignKey(
        'ProjectPhase', blank=True, null=True, on_delete=models.SET_NULL
    )
    board = models.ForeignKey(
        'ConnectwiseBoard', blank=True, null=True, on_delete=models.SET_NULL)
    company = models.ForeignKey(
        'Company', blank=True, null=True, related_name='company_tickets',
        on_delete=models.SET_NULL)
    company_site = models.ForeignKey(
        'CompanySite', blank=True, null=True, on_delete=models.SET_NULL
    )
    contact = models.ForeignKey('Contact', blank=True, null=True,
                                on_delete=models.SET_NULL)
    location = models.ForeignKey(
        'Location', blank=True, null=True, related_name='location_tickets',
        on_delete=models.SET_NULL)
    system_location = models.ForeignKey(
        'SystemLocation', blank=True, null=True,
        related_name='tickets', on_delete=models.SET_NULL)
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
    source = models.ForeignKey(
        'Source', blank=True, null=True, related_name='source_tickets',
        on_delete=models.SET_NULL)
    work_type = models.ForeignKey(
        'WorkType', blank=True, null=True, related_name='work_type_tickets',
        on_delete=models.SET_NULL)
    work_role = models.ForeignKey(
        'WorkRole', blank=True, null=True, related_name='work_role_tickets',
        on_delete=models.SET_NULL)

    class Meta:
        verbose_name = 'Ticket'
        verbose_name_plural = 'Tickets'
        ordering = ('summary', )

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
        # TODO
        #  This _update_cw method just passes in the field names and the
        #  new data to be updated from those field names of only the ones to be
        #  changed.
        #  Other than that, none of this needs to be on the model class, it
        #  is only here for backwards compatibility until issue 2861

        # TODO Right now updating and creating records is split between
        #  Synchronizers and models. We need to refactor to have all
        #  interaction with the PSA to be through synchronizers.
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


class NonInternalNoteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().exclude(internal_analysis_flag=True)


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

    objects = models.Manager()
    non_internal_objects = NonInternalNoteManager()

    class Meta:
        ordering = ('-date_created', 'id')
        verbose_name_plural = 'Notes'

    @property
    def note(self):
        return self.text

    def __str__(self):
        return 'Ticket {} note: {}'.format(self.ticket, str(self.date_created))

    def get_entered_time(self):
        return self.date_created

    def get_time_start(self):
        return self.date_created

    def get_time_end(self):
        return None

    def get_time_actual(self):
        return None

    def get_sort_date(self):
        """
        Return the appropriate date field of the given item. Used for sorting
        service notes and time entries together.
        """
        date_field = self.date_created

        # In the unlikely event of one of the date fields being null simply
        # use the time when the item was inserted in database.
        if not date_field:
            date_field = self.created

        return date_field

    def update_cw(self, **kwargs):
        api_class = self.ticket.api_class

        api_client = api_class(
            api_public_key=kwargs.get('api_public_key'),
            api_private_key=kwargs.get('api_private_key')
        )
        return api_client.update_note(self)


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
    members = models.ManyToManyField(
        'Member',
        through='ScheduleEntry',
        related_name='member_activities'
    )

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


class Type(TimeStampedModel):
    name = models.CharField(max_length=50)
    board = models.ForeignKey('ConnectWiseBoard', on_delete=models.CASCADE)
    inactive_flag = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Type'
        verbose_name_plural = 'Types'

    def __str__(self):
        return "{}/{}".format(self.board, self.name)


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

    def get_connectwise_url(self):
        params = dict(
            recordType='AgreementFV',
            recid=self.id,
            companyName=settings.CONNECTWISE_CREDENTIALS['company_id']
        )
        return '{}/{}?{}'.format(
            settings.CONNECTWISE_SERVER_URL,
            settings.CONNECTWISE_TICKET_PATH,
            urllib.parse.urlencode(params)
        )


class Source(TimeStampedModel):
    name = models.CharField(max_length=100, blank=False, null=False)
    default_flag = models.BooleanField()

    def __str__(self):
        return self.name


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


class ContactTypeTracker(ContactType):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_contacttype'


class CompanyNoteTypeTracker(CompanyNoteType):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_companynotetype'


class CompanyTeamTracker(CompanyTeam):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_companyteam'


class CompanySiteTracker(CompanySite):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_companysite'


class CompanyTeamRoleTracker(CompanyTeamRole):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_companyteamrole'


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


class SystemLocationTracker(SystemLocation):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_systemlocation'


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


class ConfigurationStatusTracker(ConfigurationStatus):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_configurationstatus'


class ConfigurationTypeTracker(ConfigurationType):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_configurationtype'


class ServiceNoteTracker(ServiceNote):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_servicenote'


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


class SourceTracker(Source):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_source'


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


class ProjectRoleTracker(ProjectRole):
    tracker = FieldTracker()

    class Meta:
        proxy = True
        db_table = 'djconnectwise_projectrole'


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
