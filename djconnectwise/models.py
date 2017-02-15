import os
import urllib.error
import urllib.parse
import urllib.request

from easy_thumbnails.fields import ThumbnailerImageField
from model_utils import Choices

from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.models import TimeStampedModel


class SyncJob(models.Model):
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(blank=True, null=True)


class CallBackEntry(models.Model):
    CALLBACK_TYPES = Choices(
        ('ticket', "Ticket"),
    )

    callback_type = models.CharField(max_length=25)
    url = models.CharField(max_length=255)
    level = models.CharField(max_length=255)
    object_id = models.IntegerField()
    entry_id = models.IntegerField()
    member_id = models.IntegerField()
    enabled = models.BooleanField(default=False)

    def __str__(self):
        return self.url


class ConnectWiseBoard(TimeStampedModel):
    board_id = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=255)
    inactive = models.BooleanField()

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name

    @property
    def board_statuses(self):
        return ConnectWiseBoardStatus.objects.filter(board_id=self.board_id)


class ConnectWiseBoardStatus(TimeStampedModel):
    """
    Used for looking up the status/board id combination
    """
    board_id = models.PositiveSmallIntegerField()
    status_id = models.PositiveSmallIntegerField()
    status_name = models.CharField(blank=True, null=True, max_length=250)

    class Meta:
        ordering = ('status_name',)

    def __str__(self):
        return self.status_name


class Member(TimeStampedModel):
    identifier = models.CharField(
        max_length=15, blank=False, unique=True)  # This is the CW username
    first_name = models.CharField(max_length=30, blank=False)
    last_name = models.CharField(max_length=30, blank=False)
    office_email = models.EmailField(max_length=250)
    inactive = models.BooleanField(default=False)
    avatar = ThumbnailerImageField(null=True, blank=True, verbose_name=_(
        'Member Avatar'), help_text=_('Member Avatar'))

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
        member.first_name = api_member['firstName']
        member.last_name = api_member['lastName']
        member.identifier = api_member['identifier']
        member.office_email = api_member['officeEmail']
        member.inactive = api_member['inactiveFlag']
        member.save()
        return member


class Company(TimeStampedModel):
    company_name = models.CharField(blank=True, null=True, max_length=250)
    company_alias = models.CharField(blank=True, null=True, max_length=250)
    company_identifier = models.CharField(
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
        ordering = ('company_identifier', )

    def __str__(self):
        return self.get_company_identifier() or ''

    def get_company_identifier(self):
        identifier = self.company_identifier
        if settings.DJCONNECTWISE_COMPANY_ALIAS:
            identifier = self.company_alias or self.company_identifier
        return identifier


class TicketStatus(TimeStampedModel):
    CLOSED = 'Closed'

    status_id = models.IntegerField(blank=True, null=True, unique=True)
    # might ditch this field, it seems to always contain same value as
    # status_name
    ticket_status = models.CharField(blank=True, null=True, max_length=250)
    status_name = models.CharField(blank=True, null=True, max_length=250)

    class Meta:
        verbose_name_plural = 'ticket statuses'
        ordering = ('ticket_status',)

    def __str__(self):
        return self.status_name


class TicketPriority(TimeStampedModel):
    name = models.CharField(max_length=50, blank=False)
    priority_id = models.PositiveSmallIntegerField()
    sort = models.PositiveSmallIntegerField()
    color = models.CharField(max_length=50, blank=False)

    class Meta:
        verbose_name_plural = 'ticket priorities'
        ordering = ('name', )

    def __str__(self):
        return self.name


class ServiceTicketAssignment(TimeStampedModel):
    service_ticket = models.ForeignKey('ServiceTicket')
    member = models.ForeignKey('Member')


class Project(TimeStampedModel):
    name = models.CharField(max_length=200)
    project_id = models.PositiveSmallIntegerField()
    project_href = models.CharField(max_length=200)

    class Meta:
        ordering = ('name', )

    def __str__(self):
        return self.name or ''


class ServiceTicket(TimeStampedModel):
    RECORD_TYPES = (
        ('ServiceTicket', "Service Ticket"),
        ('ProjectTicket', "Project Ticket"),
        ('ProjectIssue', "Project Issue"),
    )

    closed_flag = models.NullBooleanField(blank=True, null=True)
    type = models.CharField(blank=True, null=True, max_length=250)
    sub_type = models.CharField(blank=True, null=True, max_length=250)
    sub_type_item = models.CharField(blank=True, null=True, max_length=250)
    priority_text = models.CharField(blank=True, null=True, max_length=250)
    location = models.CharField(blank=True, null=True, max_length=250)
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
    team_id = models.IntegerField(blank=True, null=True)
    agreement_id = models.IntegerField(blank=True, null=True)
    severity = models.CharField(blank=True, null=True, max_length=250)
    impact = models.CharField(blank=True, null=True, max_length=250)
    date_resolved_utc = models.DateTimeField(blank=True, null=True)
    date_resplan_utc = models.DateTimeField(blank=True, null=True)
    date_responded_utc = models.DateTimeField(blank=True, null=True)
    is_in_sla = models.NullBooleanField(blank=True, null=True)
    api_text = models.TextField(blank=True, null=True)
    board_name = models.CharField(blank=True, null=True, max_length=250)
    board_id = models.IntegerField(blank=True, null=True, db_index=True)
    board_status_id = models.IntegerField(blank=True, null=True)
    priority = models.ForeignKey('TicketPriority', blank=True, null=True)
    status = models.ForeignKey(
        'TicketStatus', blank=True, null=True, related_name='status_tickets')
    company = models.ForeignKey(
        'Company', blank=True, null=True, related_name='company_tickets')
    project = models.ForeignKey(
        'Project', blank=True, null=True, related_name='project_tickets')
    members = models.ManyToManyField(
        'Member', through='ServiceTicketAssignment',
        related_name='member_tickets')
    # TODO: add FK to ConnectWiseBoard

    class Meta:
        # ordering = ['priority_text','entered_date_utc','id']
        verbose_name = 'Service Ticket'
        verbose_name_plural = 'Service Tickets'
        ordering = ('summary', )

    def __str__(self):
        try:
            return '{0:8d}-{1:100}'.format(self.id, self.summary)
        except:
            return '{0:8d}-{1:100}'.format(self.id,
                                           self.summary.encode('utf8'))

    def get_connectwise_url(self):
        params = dict(
            locale='en_US',
            recordType='ServiceFv',
            recid=self.id,
            companyName=settings.CONNECTWISE_CREDENTIALS['company_id']
        )

        ticket_url = os.path.join(
            settings.CONNECTWISE_SERVER_URL,
            settings.CONNECTWISE_TICKET_PATH,
            '?{0}'.format(urllib.parse.urlencode(params))
        )

        return ticket_url

    def time_remaining(self):
        time_remaining = self.budget_hours
        if self.budget_hours and self.actual_hours:
            time_remaining = self.budget_hours - self.actual_hours
        return time_remaining
