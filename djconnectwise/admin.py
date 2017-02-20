# -*- coding: utf-8 -*-
from django.contrib import admin

from . import models


@admin.register(models.ConnectWiseBoard)
class ConnectWiseBoardAdmin(admin.ModelAdmin):
    list_display = ('name', 'board_id', 'inactive')
    search_fields = ['name']


@admin.register(models.TicketStatus)
class TicketStatusAdmin(admin.ModelAdmin):
    list_display = ('status_id', 'status_name')
    search_fields = ['status_name']


@admin.register(models.Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('identifier', 'full_name', 'office_email')
    search_fields = ('identifier', 'first_name', 'last_name', 'office_email')

    def full_name(self, obj):
        return str(obj)


@admin.register(models.Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('id', 'company_name',
                    'company_identifier', 'type', 'status')
    list_filter = ('status',)
    search_fields = ['company_name', 'company_identifier']


@admin.register(models.ServiceTicket)
class ServiceTicketAdmin(admin.ModelAdmin):
    list_display = ('summary', 'status', 'resources', 'record_type',)

    list_filter = ('status', 'record_type',)
    search_fields = ['id', 'summary', 'members__user__username', ]

    def resources(self, obj):
        return ', '.join([str(m) for m in obj.members.all()])


@admin.register(models.TicketPriority)
class TicketPriorityAdmin(admin.ModelAdmin):
    model = models.TicketPriority
    list_display = ('priority_id', 'name', 'sort', 'color')


@admin.register(models.Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('team_id', 'name', 'board')


@admin.register(models.Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('location_id', 'name', 'where')
