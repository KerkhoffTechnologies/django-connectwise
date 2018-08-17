import re
import logging
import urllib

from easy_thumbnails.fields import ThumbnailerImageField
from model_utils import Choices

from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.models import TimeStampedModel

from . import api

logger = logging.getLogger(__name__)


PRIORITY_RE = re.compile('^Priority ([\d]+)')


class InvalidStatusError(Exception):
    pass


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


class CallBackEntry(models.Model):
    TICKET = 'ticket'
    PROJECT = 'project'
    COMPANY = 'company'
    OPPORTUNITY = 'opportunity'

    CALLBACK_TYPES = Choices(
        (COMPANY, "Company"),
        (OPPORTUNITY, "Opportunity"),
        (PROJECT, "Project"),
        (TICKET, "Ticket"),
    )

    description = models.CharField(max_length=100, null=True, blank=True)
    callback_type = models.CharField(max_length=25)
    url = models.CharField(max_length=255)
    level = models.CharField(max_length=255)
    object_id = models.IntegerField()
    member = models.ForeignKey('Member', null=True,  on_delete=models.SET_NULL)
    inactive_flag = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Callback entry'
        verbose_name_plural = 'Callback entries'

    def __str__(self):
        return self.url


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

    name = models.CharField(blank=True, null=True, max_length=250)
    sort_order = models.PositiveSmallIntegerField()
    display_on_board = models.BooleanField()
    inactive = models.BooleanField()
    closed_status = models.BooleanField()
    board = models.ForeignKey('ConnectWiseBoard', on_delete=models.CASCADE)

    objects = models.Manager()
    available_objects = AvailableBoardStatusManager()

    class Meta:
        ordering = ('board__name', 'sort_order', 'name')
        verbose_name_plural = 'Board statuses'

    def __str__(self):
        return '{}/{}'.format(self.board, self.name)


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
    last_name = models.CharField(max_length=30, blank=False)
    office_email = models.EmailField(max_length=250)
    inactive = models.BooleanField(default=False)
    avatar = ThumbnailerImageField(
        null=True, blank=True,
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
        return '{} {}'.format(self.first_name, self.last_name)

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

    name = models.CharField(max_length=250)
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
        ('NoDefault', "No Default")
    )

    class Meta:
        verbose_name_plural = 'Time entries'
        ordering = ('-time_start', 'id')

    def __str__(self):
        return str(self.id) or ''

    actual_hours = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=6)
    billable_option = models.CharField(choices=BILL_TYPES, max_length=250)
    charge_to_type = models.CharField(choices=CHARGE_TYPES, max_length=250)
    hours_deduct = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=6)
    internal_notes = models.TextField(blank=True, null=True, max_length=2000)
    notes = models.TextField(blank=True, null=True, max_length=2000)
    time_start = models.DateTimeField(blank=True, null=True)
    time_end = models.DateTimeField(blank=True, null=True)

    detail_description_flag = models.BooleanField(default=False)
    internal_analysis_flag = models.BooleanField(default=False)
    resolution_flag = models.BooleanField(default=False)

    charge_to_id = models.ForeignKey(
        'Ticket', blank=True, null=True, on_delete=models.CASCADE)
    company = models.ForeignKey(
        'Company', blank=False, null=False, on_delete=models.CASCADE)
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
        blank=True, null=True, decimal_places=2, max_digits=6)
    budget_hours = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=6)
    scheduled_hours = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=6)

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
    Return only Opportunity Statuses whose closed field is False.
    """
    def get_queryset(self):
        return super().get_queryset().filter(
            closed_flag=False,
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
                                 on_delete=models.CASCADE)
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

    actual_hours = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=6)
    agreement_id = models.IntegerField(blank=True, null=True)
    approved = models.NullBooleanField(blank=True, null=True)
    budget_hours = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=6)
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
    sub_type = models.CharField(blank=True, null=True, max_length=250)
    sub_type_item = models.CharField(blank=True, null=True, max_length=250)
    summary = models.CharField(blank=True, null=True, max_length=250)
    updated_by = models.CharField(blank=True, null=True, max_length=250)

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

    class Meta:
        verbose_name = 'Ticket'
        verbose_name_plural = 'Tickets'
        ordering = ('summary', )

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
        Send ticket status and closed_flag updates to ConnectWise.
        """
        service_client = api.ServiceAPIClient()
        return service_client.update_ticket_status(
            self.id, self.closed_flag, self.status
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


class Sla(TimeStampedModel):

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


class SlaPriority(TimeStampedModel):

    sla = models.ForeignKey(
        'Sla',
        on_delete=models.CASCADE
        )
    priority = models.ForeignKey(
        'TicketPriority',
        on_delete=models.CASCADE
        )
    respond_hours = models.BigIntegerField()
    plan_within = models.BigIntegerField()
    resolution_hours = models.BigIntegerField()

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
