from django.contrib import admin
from django.db import models as db_models
from django.forms import TextInput
import datetime

from . import models


@admin.register(models.SyncJob)
class SyncJobAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'start_time', 'end_time', 'duration_or_zero', 'entity_name',
        'success', 'added', 'updated', 'deleted', 'sync_type',
    )
    list_filter = ('sync_type', 'success', 'entity_name', )

    def duration_or_zero(self, obj):
        """
        Return the duration, or just the string 0 (otherwise we get 0:00:00)
        """
        duration = obj.duration()
        if duration:
            # Get rid of the microseconds part
            duration_seconds = duration - datetime.timedelta(
                microseconds=duration.microseconds
            )
            return duration_seconds if duration_seconds else '0'
    duration_or_zero.short_description = 'Duration'


@admin.register(models.ConnectWiseBoard)
class ConnectWiseBoardAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'inactive')
    search_fields = ['name']
    list_filter = ('inactive',)


@admin.register(models.BoardStatus)
class BoardStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'board', 'name', 'closed_status')
    search_fields = ['name', 'board__name']


@admin.register(models.ServiceNote)
class ServiceNoteAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticket', 'date_created', 'member', 'text',
                    'created_by', 'internal_flag', 'external_flag',
                    'detail_description_flag', 'internal_analysis_flag'
                    )
    search_fields = ['id', 'date_created', 'text', 'created_by']


@admin.register(models.OpportunityNote)
class OpportunityNoteAdmin(admin.ModelAdmin):
    list_display = ('id', 'opportunity', 'text')
    search_fields = ['id', 'text']


@admin.register(models.Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'where')


@admin.register(models.Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = (
        'identifier', 'full_name', 'office_email', 'inactive',
        'license_class'
    )
    search_fields = ('identifier', 'first_name', 'last_name', 'office_email')
    list_filter = ('license_class', 'inactive', )

    def full_name(self, obj):
        return str(obj)


@admin.register(models.Territory)
class TerritoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ['id', 'name']


@admin.register(models.Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('id', 'name',
                    'identifier', 'company_type', 'status', 'deleted_flag')
    list_filter = ('status',)
    search_fields = ['name', 'identifier']


@admin.register(models.CompanyStatus)
class CompanyStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'default_flag', 'inactive_flag')


@admin.register(models.CompanyType)
class CompanyTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'vendor_flag')
    search_fields = ['name']


@admin.register(models.ScheduleType)
class ScheduleTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'identifier')
    search_fields = ['name']


@admin.register(models.ScheduleStatus)
class ScheduleStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ['name']


@admin.register(models.ScheduleEntry)
class ScheduleEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticket_object', 'activity_object', 'member',
                    'done_flag',
                    'status', 'expected_date_start', 'expected_date_end',)
    list_filter = ('status', 'done_flag', 'member')
    search_fields = ['name', 'ticket_object__id',
                     'activity_object__id', 'member__identifier']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            'ticket_object', 'activity_object', 'member', 'status'
        )


@admin.register(models.TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'charge_to_id', 'charge_to_type',
                    'member', 'billable_option', 'actual_hours',
                    'time_start', 'time_end', 'hours_deduct', 'notes',
                    'internal_notes')
    list_filter = ('member', 'charge_to_type')
    search_fields = ['id', 'charge_to_id__id', 'member__identifier',
                     'charge_to_type']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('company', 'member', 'charge_to_id')


@admin.register(models.Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'board')


@admin.register(models.TicketPriority)
class TicketPriorityAdmin(admin.ModelAdmin):
    model = models.TicketPriority
    list_display = ('id', 'name', 'sort', 'color')


@admin.register(models.ProjectStatus)
class ProjectStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'default_flag', 'inactive_flag',
                    'closed_flag')
    list_filter = ('default_flag', 'inactive_flag', 'closed_flag',)
    search_fields = ['name']


@admin.register(models.Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'status', )
    list_filter = ('status', )
    search_fields = ['name']


@admin.register(models.OpportunityStage)
class OpportunityStageAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')


@admin.register(models.OpportunityStatus)
class OpportunityStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'won_flag', 'lost_flag',
                    'closed_flag', 'inactive_flag')
    list_filter = ('won_flag', 'lost_flag', 'closed_flag', 'inactive_flag')
    search_fields = ['name']


@admin.register(models.OpportunityPriority)
class OpportunityPriorityAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')


@admin.register(models.OpportunityType)
class OpportunityTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'description', 'inactive_flag')


@admin.register(models.Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'stage', 'status', 'opportunity_type')
    list_filter = ('stage', 'status', 'opportunity_type')
    search_fields = ['name']


class ScheduleEntryInline(admin.StackedInline):
    model = models.ScheduleEntry


@admin.register(models.Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'summary', 'status', 'record_type',)
    list_filter = ('status', 'record_type')
    search_fields = ['id', 'summary', 'company__name']

    inlines = [
        ScheduleEntryInline
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('status', 'status__board')


@admin.register(models.ActivityStatus)
class ActivityStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'inactive_flag', 'closed_flag')
    list_filter = ('inactive_flag', 'closed_flag')
    search_fields = ['name']


@admin.register(models.ActivityType)
class ActivityTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'points', 'inactive_flag')
    list_filter = ('inactive_flag',)
    search_fields = ['name']


@admin.register(models.Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'notes', 'date_start', 'date_end',
                    'assign_to', 'opportunity', 'ticket')
    search_fields = [
        'name', 'notes', 'ticket__summary', 'opportunity__name',
        'company__name'
    ]
    list_filter = ('status', 'type')

    formfield_overrides = {
        db_models.CharField: {'widget': TextInput(attrs={'size': '40'})}
    }

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('ticket', 'opportunity', 'assign_to')


@admin.register(models.SalesProbability)
class SalesProbabilityAdmin(admin.ModelAdmin):
    list_display = ('id', 'probability',)


class SlaPriorityInline(admin.StackedInline):
    model = models.SlaPriority


@admin.register(models.Sla)
class SlaAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'default_flag', 'respond_hours',
                    'plan_within', 'resolution_hours')
    search_fields = ['name', 'respond_hours',
                     'plan_within', 'resolution_hours']
    inlines = [
        SlaPriorityInline
    ]


@admin.register(models.SlaPriority)
class SlaPriorityAdmin(admin.ModelAdmin):
    list_display = ('id', 'sla', 'priority', 'respond_hours',
                    'plan_within', 'resolution_hours')
    list_filter = ['sla', 'priority']
    search_fields = ['sla', 'priority', 'respond_hours',
                     'plan_within', 'resolution_hours']


@admin.register(models.Calendar)
class CalendarAdmin(admin.ModelAdmin):
    list_display = ('id', 'name',)
    search_fields = ['name']


@admin.register(models.MyCompanyOther)
class MyCompanyOtherAdmin(admin.ModelAdmin):
    list_display = ('id', 'default_calendar',)


@admin.register(models.Holiday)
class Holiday(admin.ModelAdmin):
    list_display = ('id', 'name', 'date')
    search_fields = ['name', 'date']


@admin.register(models.HolidayList)
class HolidayList(admin.ModelAdmin):
    list_display = ('id', 'name',)
    search_fields = ['name']


@admin.register(models.Type)
class Type(admin.ModelAdmin):
    list_display = ('id', 'name', 'board',)
    search_fields = ['name']


@admin.register(models.SubType)
class SubType(admin.ModelAdmin):
    list_display = ('id', 'name', 'board',)
    search_fields = ['name']


@admin.register(models.Item)
class Item(admin.ModelAdmin):
    list_display = ('id', 'name', 'board',)
    search_fields = ['name']


@admin.register(models.WorkType)
class WorkType(admin.ModelAdmin):
    list_display = ('id', 'name', 'inactive_flag',)
    search_fields = ['name']


@admin.register(models.WorkRole)
class WorkRole(admin.ModelAdmin):
    list_display = ('id', 'name', 'inactive_flag',)
    search_fields = ['name']


@admin.register(models.Agreement)
class Agreement(admin.ModelAdmin):
    list_display = ('id', '__str__', 'company', 'cancelled_flag',
                    'bill_time', 'work_type', 'work_role')
    search_fields = ['name']
