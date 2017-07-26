# -*- coding: utf-8 -*-
from django.contrib import admin

from . import models


@admin.register(models.ConnectWiseBoard)
class ConnectWiseBoardAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'inactive')
    search_fields = ['name']


@admin.register(models.BoardStatus)
class BoardStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'board', 'name')
    search_fields = ['name', 'board__name']


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


@admin.register(models.Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'status_name')
    list_filter = ('name', 'status_name')
    search_fields = ['name']


# class ResourceInline(admin.TabularInline):
#     model = models.Ticket.members.through
#     extra = 0


@admin.register(models.Ticket)
class TicketAdmin(admin.ModelAdmin):
    # list_display = ('id', 'summary', 'status', 'resources', 'record_type',)
    list_display = ('id', 'summary', 'status', 'record_type',)

    list_filter = ('status', 'record_type')
    search_fields = ['id', 'summary', 'company__name']
    # inlines = [ResourceInline]

    # def resources(self, obj):
    #     return ', '.join([str(m) for m in obj.members.all()])


@admin.register(models.TicketPriority)
class TicketPriorityAdmin(admin.ModelAdmin):
    model = models.TicketPriority
    list_display = ('id', 'name', 'sort', 'color')


@admin.register(models.Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'board')


@admin.register(models.Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'where')


@admin.register(models.SyncJob)
class SyncJobAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'start_time', 'end_time', 'entity_name', 'success', 'added',
        'updated', 'deleted'
    )
    list_filter = ('entity_name', )


@admin.register(models.OpportunityStatus)
class OpportunityStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'won_flag', 'lost_flag',
                    'closed_flag', 'inactive_flag')
    list_filter = ('won_flag', 'lost_flag', 'closed_flag', 'inactive_flag')
    search_fields = ['name']


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
                    'done_flag', 'object', 'member', 'where',
                    'status', 'schedule_type')
    list_filter = ('name', 'member', 'where', 'status')
    search_fields = ['name', 'object', 'member']
