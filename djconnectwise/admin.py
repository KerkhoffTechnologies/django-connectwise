from django.contrib import admin
from django.db import models as db_models
from django.forms import TextInput

from . import models


@admin.register(models.SyncJob)
class SyncJobAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'start_time', 'end_time', 'entity_name', 'success', 'added',
        'updated', 'deleted'
    )
    list_filter = ('entity_name', )


@admin.register(models.CallBackEntry)
class CallBackEntryAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'description', 'callback_type', 'url', 'level'
    )


@admin.register(models.ConnectWiseBoard)
class ConnectWiseBoardAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'inactive')
    search_fields = ['name']


@admin.register(models.BoardStatus)
class BoardStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'board', 'name')
    search_fields = ['name', 'board__name']


@admin.register(models.Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'where')


@admin.register(models.Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('identifier', 'full_name', 'office_email', 'license_class')
    search_fields = ('identifier', 'first_name', 'last_name', 'office_email')

    def full_name(self, obj):
        return str(obj)


@admin.register(models.Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('id', 'name',
                    'identifier', 'type', 'status', 'deleted_flag')
    list_filter = ('status',)
    search_fields = ['name', 'identifier']


@admin.register(models.CompanyStatus)
class CompanyStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'default_flag', 'inactive_flag')


@admin.register(models.ScheduleType)
class ScheduleTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'identifier')
    list_filter = ('name', )
    search_fields = ['name']


@admin.register(models.ScheduleStatus)
class ScheduleStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    list_filter = ('name', )
    search_fields = ['name']


@admin.register(models.ScheduleEntry)
class ScheduleEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'expected_date_start', 'expected_date_end',
                    'done_flag', 'ticket_object', 'activity_object', 'member',
                    'where', 'status', 'schedule_type')
    list_filter = ('name', 'member', 'where', 'status')
    search_fields = ['name', 'ticket_object', 'activity_object', 'member']


@admin.register(models.Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'board')


@admin.register(models.TicketPriority)
class TicketPriorityAdmin(admin.ModelAdmin):
    model = models.TicketPriority
    list_display = ('id', 'name', 'sort', 'color')


@admin.register(models.Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'status_name')
    list_filter = ('name', 'status_name')
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


@admin.register(models.Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'notes', 'date_start', 'date_end',
                    'assign_to', 'opportunity', 'ticket')
    list_filter = ['opportunity', ]
    search_fields = ['name', 'notes']

    formfield_overrides = {
        db_models.CharField: {'widget': TextInput(attrs={'size': '40'})}
    }
