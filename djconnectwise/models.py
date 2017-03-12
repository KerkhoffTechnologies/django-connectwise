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


class InvalidStatusError(Exception):
    pass

PRIORITY_RE = re.compile('^Priority ([\d]+)')


class SyncJob(models.Model):
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(blank=True, null=True)


class CallBackEntry(models.Model):
    TICKET = 'ticket'
    PROJECT = 'project'
    COMPANY = 'company'

    CALLBACK_TYPES = Choices(
        (COMPANY, "Company"),
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

    def __str__(self):
        return self.url


class ActiveConnectWiseBoardManager(models.Manager):
    """Return only active ConnectWise boards."""
    def get_queryset(self):
        return super().get_queryset().filter(inactive=False)


class AllConnectWiseBoardManager(models.Manager):
    """Return all ConnectWise boards."""
    def get_queryset(self):
        return super().get_queryset().all()


class ConnectWiseBoard(TimeStampedModel):
    name = models.CharField(max_length=255)
    inactive = models.BooleanField(default=False)

    objects = ActiveConnectWiseBoardManager()
    all_objects = AllConnectWiseBoardManager()

    class Meta:
        ordering = ('name',)
        verbose_name = 'ConnectWise board'

    def __str__(self):
        return self.name

    @property
    def board_statuses(self):
        return BoardStatus.objects.filter(board=self)

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


class ActiveBoardStatusManager(models.Manager):
    """Return only statuses whose ConnectWise board is active."""
    def get_queryset(self):
        return super().get_queryset().filter(board__inactive=False)


class AllBoardManager(models.Manager):
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

    objects = ActiveBoardStatusManager()
    all_objects = AllBoardManager()

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


class NotAPIMemberManager(models.Manager):
    """Return members that aren't API members."""
    def get_queryset(self):
        return super().get_queryset().exclude(license_class='A')


class AllMemberManager(models.Manager):
    """Return all members."""
    def get_queryset(self):
        return super().get_queryset().all()


class Member(TimeStampedModel):
    LICENSE_CLASSES = (
        ('F', 'Full license'),
        ('A', 'API license'),
    )

    identifier = models.CharField(
        max_length=15, blank=False, unique=True)  # This is the CW username
    first_name = models.CharField(max_length=30, blank=False)
    last_name = models.CharField(max_length=30, blank=False)
    office_email = models.EmailField(max_length=250)
    inactive = models.BooleanField(default=False)
    avatar = ThumbnailerImageField(null=True, blank=True, verbose_name=_(
        'Member Avatar'), help_text=_('Member Avatar'))
    license_class = models.CharField(
        blank=True, null=True, max_length=20,
        choices=LICENSE_CLASSES, db_index=True
    )

    objects = NotAPIMemberManager()
    all_objects = AllMemberManager()

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

    @staticmethod
    def create_member(api_member):
        member = Member()
        member.id = api_member['id']
        member.first_name = api_member['firstName']
        member.last_name = api_member['lastName']
        member.identifier = api_member['identifier']
        member.office_email = api_member['officeEmail']
        member.license_class = api_member['licenseClass']
        member.inactive = api_member['inactiveFlag']
        member.save()
        return member


class Company(TimeStampedModel):
    name = models.CharField(blank=True, null=True, max_length=250)
    company_alias = models.CharField(blank=True, null=True, max_length=250)
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
    status = models.CharField(blank=True, null=True, max_length=250)
    territory = models.CharField(blank=True, null=True, max_length=250)
    website = models.CharField(blank=True, null=True, max_length=250)
    market = models.CharField(blank=True, null=True, max_length=250)
    defaultcontactid = models.IntegerField(blank=True, null=True)
    defaultbillingcontactid = models.IntegerField(blank=True, null=True)
    updatedby = models.CharField(blank=True, null=True, max_length=250)
    lastupdated = models.CharField(blank=True, null=True, max_length=250)

    class Meta:
        verbose_name_plural = 'companies'
        ordering = ('identifier', )

    def __str__(self):
        return self.get_identifier() or ''

    def get_identifier(self):
        identifier = self.identifier
        if settings.DJCONNECTWISE_COMPANY_ALIAS:
            identifier = self.company_alias or self.identifier
        return identifier


class Team(TimeStampedModel):
    name = models.CharField(max_length=30)
    board = models.ForeignKey('ConnectWiseBoard')
    members = models.ManyToManyField('Member')

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


class TicketAssignment(TimeStampedModel):
    ticket = models.ForeignKey('Ticket')
    member = models.ForeignKey('Member')

    def __str__(self):
        return '{}: {}'.format(self.service_ticket, self.member)


class NotClosedProjectManager(models.Manager):
    """Return only projects whose status isn't "Closed"."""
    def get_queryset(self):
        return super().get_queryset().exclude(status_name='Closed')


class AllProjectManager(models.Manager):
    """Return all projects."""
    def get_queryset(self):
        return super().get_queryset().all()


class Project(TimeStampedModel):
    name = models.CharField(max_length=200)
    project_href = models.CharField(max_length=200, blank=True, null=True)
    # Project statuses aren't available as a first-class object in the API, so
    # just keep the name here for simplicity.
    status_name = models.CharField(max_length=200, blank=True, null=True)

    objects = NotClosedProjectManager()
    all_objects = AllProjectManager()

    class Meta:
        ordering = ('name', )

    def __str__(self):
        return self.name or ''


class Ticket(TimeStampedModel):
    RECORD_TYPES = (
        ('Ticket', "Service Ticket"),
        ('ProjectTicket', "Project Ticket"),
        ('ProjectIssue', "Project Issue"),
    )

    closed_flag = models.NullBooleanField(blank=True, null=True)
    type = models.CharField(blank=True, null=True, max_length=250)
    sub_type = models.CharField(blank=True, null=True, max_length=250)
    sub_type_item = models.CharField(blank=True, null=True, max_length=250)
    source = models.CharField(blank=True, null=True, max_length=250)
    summary = models.CharField(blank=True, null=True, max_length=250)
    entered_date_utc = models.DateTimeField(blank=True, null=True)
    last_updated_utc = models.DateTimeField(blank=True, null=True)
    resources = models.CharField(blank=True, null=True, max_length=250)
    required_date_utc = models.DateTimeField(blank=True, null=True)
    closed_date_utc = models.DateTimeField(blank=True, null=True)
    site_name = models.CharField(blank=True, null=True, max_length=250)
    budget_hours = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=6)
    actual_hours = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=6)
    approved = models.NullBooleanField(blank=True, null=True)
    closed_by = models.CharField(blank=True, null=True, max_length=250)
    resolve_mins = models.IntegerField(blank=True, null=True)
    res_plan_mins = models.IntegerField(blank=True, null=True)
    respond_mins = models.IntegerField(blank=True, null=True)
    updated_by = models.CharField(blank=True, null=True, max_length=250)
    record_type = models.CharField(blank=True, null=True,
                                   max_length=250, choices=RECORD_TYPES,
                                   db_index=True)
    agreement_id = models.IntegerField(blank=True, null=True)
    severity = models.CharField(blank=True, null=True, max_length=250)
    impact = models.CharField(blank=True, null=True, max_length=250)
    date_resolved_utc = models.DateTimeField(blank=True, null=True)
    date_resplan_utc = models.DateTimeField(blank=True, null=True)
    date_responded_utc = models.DateTimeField(blank=True, null=True)
    is_in_sla = models.NullBooleanField(blank=True, null=True)
    api_text = models.TextField(blank=True, null=True)

    board = models.ForeignKey('ConnectwiseBoard', blank=True, null=True)
    priority = models.ForeignKey('TicketPriority', blank=True, null=True)
    status = models.ForeignKey(
        'BoardStatus', blank=True, null=True, related_name='status_tickets')
    company = models.ForeignKey(
        'Company', blank=True, null=True, related_name='company_tickets')
    location = models.ForeignKey(
        'Location', blank=True, null=True, related_name='location_tickets')
    team = models.ForeignKey(
        'Team', blank=True, null=True, related_name='team_tickets')
    project = models.ForeignKey(
        'Project', blank=True, null=True, related_name='project_tickets')
    members = models.ManyToManyField(
        'Member', through='TicketAssignment',
        related_name='member_tickets')

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

        ticket_url = '{}/{}?{}'.format(
            settings.CONNECTWISE_SERVER_URL,
            settings.CONNECTWISE_TICKET_PATH,
            urllib.parse.urlencode(params)
        )

        return ticket_url

    def save(self, *args, **kwargs):
        """
        Save the ticket.

        If update_cw as a kwarg is True, then update ConnectWise with changes.
        """
        self._check_valid_status()

        update_cw = kwargs.pop('update_cw', False)
        super().save(*args, **kwargs)
        if update_cw:
            self.update_cw()

    def _check_valid_status(self):
        """
        Raise InvalidStatusError if the status doesn't belong to the board.

        If status or board are None, then don't bother, since this can happen
        during sync jobs and it would be a lot of work to enforce at all the
        right times.
        """
        if self.status and self.board and self.status.board != self.board:
            raise InvalidStatusError(
                "{} (ID {}) is not a valid status for the ticket's "
                "ConnectWise board ({}, ID {}).".
                format(
                    self.status.name,
                    self.status.id,
                    self.board,
                    self.board.id,
                )
            )

    def update_cw(self):
        """
        Send ticket updates to ConnectWise.

        TODO: this only actually sends updates for the status and closedFlag
        fields.
        """
        service_client = api.ServiceAPIClient()
        api_ticket = service_client.get_ticket(self.id)

        api_ticket['closedFlag'] = self.closed_flag
        api_ticket['status'] = {
            'id': self.status.id,
            'name': self.status.name,
        }

        # No need for a callback update when updating via API
        api_ticket['skipCallback'] = True
        return service_client.update_ticket(api_ticket)

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
