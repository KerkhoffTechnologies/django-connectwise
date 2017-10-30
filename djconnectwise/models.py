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
    member = models.ForeignKey('Member')
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


class ConnectWiseBoardManager(models.Manager):
    """Return all ConnectWise boards."""
    def get_queryset(self):
        return super().get_queryset().all()


class ConnectWiseBoard(TimeStampedModel):
    name = models.CharField(max_length=255)
    inactive = models.BooleanField(default=False)

    objects = ConnectWiseBoardManager()
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


class BoardStatusManager(models.Manager):
    """Return all ConnectWise board statuses."""
    def get_queryset(self):
        return super().get_queryset().all()


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
    board = models.ForeignKey('ConnectWiseBoard')

    objects = BoardStatusManager()
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


class MemberManager(models.Manager):
    """Return all members."""
    def get_queryset(self):
        return super().get_queryset().all()


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

    objects = MemberManager()
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


class CompanyManager(models.Manager):
    """Return all companies."""
    def get_queryset(self):
        return super().get_queryset().all()


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
    type = models.CharField(blank=True, null=True, max_length=250)
    territory = models.CharField(blank=True, null=True, max_length=250)
    website = models.CharField(blank=True, null=True, max_length=250)
    market = models.CharField(blank=True, null=True, max_length=250)
    defaultcontactid = models.IntegerField(blank=True, null=True)
    defaultbillingcontactid = models.IntegerField(blank=True, null=True)
    updatedby = models.CharField(blank=True, null=True, max_length=250)
    lastupdated = models.CharField(blank=True, null=True, max_length=250)
    deleted_flag = models.BooleanField(default=False)
    status = models.ForeignKey('CompanyStatus', blank=True, null=True)

    objects = CompanyManager()
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
    name = models.CharField(max_length=250)
    expected_date_start = models.DateTimeField(blank=True, null=True)
    expected_date_end = models.DateTimeField(blank=True, null=True)
    done_flag = models.BooleanField(default=False)

    ticket_object = models.ForeignKey('Ticket', blank=True, null=True)
    activity_object = models.ForeignKey('Activity', blank=True, null=True)
    member = models.ForeignKey('Member')
    where = models.ForeignKey('Location', blank=True, null=True)
    status = models.ForeignKey('ScheduleStatus', blank=True, null=True)
    schedule_type = models.ForeignKey('ScheduleType', blank=True, null=True)

    class Meta:
        verbose_name_plural = 'Schedule entries'
        ordering = ('name', )

    def __str__(self):
        return self.name


class AvailableBoardTeamManager(models.Manager):
    """Return only teams whose ConnectWise board is active."""
    def get_queryset(self):
        return super().get_queryset().filter(board__inactive=False)


class BoardTeamManager(models.Manager):
    """Return all ConnectWise board teams."""
    def get_queryset(self):
        return super().get_queryset().all()


class Team(TimeStampedModel):
    name = models.CharField(max_length=30)
    board = models.ForeignKey('ConnectWiseBoard')
    members = models.ManyToManyField('Member')

    objects = BoardTeamManager()
    available_objects = AvailableBoardTeamManager()

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
        ordering = ('name', )

    def __str__(self):
        return self.name

    @property
    def color(self):
        """
        If a color has been set, then return it. Otherwise if the name
        matches the common format ("Priority X - ..."), then return
        something sensible based on values seen in the wild.
        """
        if self._color:
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


class AvailableProjectManager(models.Manager):
    """Return only projects whose status isn't "Closed"."""
    def get_queryset(self):
        return super().get_queryset().exclude(status_name='Closed')


class ProjectManager(models.Manager):
    """Return all projects."""
    def get_queryset(self):
        return super().get_queryset().all()


class Project(TimeStampedModel):
    name = models.CharField(max_length=200)
    # Project statuses aren't available as a first-class object in the API, so
    # just keep the name here for simplicity.
    status_name = models.CharField(max_length=200, blank=True, null=True)

    objects = ProjectManager()
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
            closed_flag=False,
        )


class OpportunityStatusManager(models.Manager):
    """Return all Opportunity statuses."""
    def get_queryset(self):
        return super().get_queryset().all()


class OpportunityStatus(TimeStampedModel):
    name = models.CharField(max_length=30)
    won_flag = models.BooleanField(default=False)
    lost_flag = models.BooleanField(default=False)
    closed_flag = models.BooleanField(default=False)
    inactive_flag = models.BooleanField(default=False)

    objects = OpportunityStatusManager()
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
    business_unit_id = models.IntegerField()
    closed_date = models.DateTimeField(blank=True, null=True)
    customer_po = models.CharField(max_length=100, blank=True, null=True)
    date_became_lead = models.DateTimeField(blank=True, null=True)
    expected_close_date = models.DateField()
    location_id = models.IntegerField()
    name = models.CharField(max_length=100)
    notes = models.TextField(blank=True, null=True)
    pipeline_change_date = models.DateTimeField(blank=True, null=True)
    source = models.CharField(max_length=100, blank=True, null=True)

    closed_by = models.ForeignKey('Member',
                                  blank=True, null=True,
                                  related_name='opportunity_closed_by')
    company = models.ForeignKey('Company', blank=True, null=True,
                                related_name='company_opportunities')
    primary_sales_rep = models.ForeignKey('Member',
                                          blank=True, null=True,
                                          related_name='opportunity_primary')
    priority = models.ForeignKey('OpportunityPriority')
    stage = models.ForeignKey('OpportunityStage')
    status = models.ForeignKey('OpportunityStatus', blank=True, null=True)
    secondary_sales_rep = models.ForeignKey(
        'Member',
        blank=True, null=True,
        related_name='opportunity_secondary')
    opportunity_type = models.ForeignKey('OpportunityType',
                                         blank=True, null=True)

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
    api_text = models.TextField(blank=True, null=True)
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
    type = models.CharField(blank=True, null=True, max_length=250)
    updated_by = models.CharField(blank=True, null=True, max_length=250)

    board = models.ForeignKey('ConnectwiseBoard', blank=True, null=True)
    company = models.ForeignKey(
        'Company', blank=True, null=True, related_name='company_tickets')
    location = models.ForeignKey(
        'Location', blank=True, null=True, related_name='location_tickets')
    members = models.ManyToManyField(
        'Member', through='ScheduleEntry',
        related_name='member_tickets')
    owner = models.ForeignKey('Member', blank=True, null=True)
    priority = models.ForeignKey('TicketPriority', blank=True, null=True)
    project = models.ForeignKey(
        'Project', blank=True, null=True, related_name='project_tickets')
    status = models.ForeignKey(
        'BoardStatus', blank=True, null=True, related_name='status_tickets')
    team = models.ForeignKey(
        'Team', blank=True, null=True, related_name='team_tickets')

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


class Activity(TimeStampedModel):
    name = models.CharField(max_length=250)
    notes = models.TextField(blank=True, null=True, max_length=2000)
    date_start = models.DateTimeField(blank=True, null=True)
    date_end = models.DateTimeField(blank=True, null=True)

    assign_to = models.ForeignKey('Member', )
    opportunity = models.ForeignKey('Opportunity', blank=True, null=True)
    ticket = models.ForeignKey('Ticket', blank=True, null=True)

    class Meta:
        verbose_name_plural = 'activities'
        # ordering = ('opportunity', 'ticket')

    def __str__(self):
        return self.get_identifier() or ''

    def get_identifier(self):
        return self.name
