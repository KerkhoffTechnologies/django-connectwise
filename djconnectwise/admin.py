# -*- coding: utf-8 -*-


from django.contrib import admin
from .models import ConnectWiseBoard, TicketStatus, ServiceTicket, Member, Company

class ConnectWiseBoardAdmin(admin.ModelAdmin):
    model = ConnectWiseBoard
    list_display = ('name', 'board_id', 'inactive')
    search_fields = ['name']


class TicketStatusAdmin(admin.ModelAdmin):
    model = TicketStatus
    list_display = ('status_id', 'status_name')
    search_fields = ['status_name']


class MemberAdmin(admin.ModelAdmin):
    model = Member
    list_display = ('identifier', 'full_name', 'office_email')
    search_fields = ('identifier', 'first_name', 'last_name', 'office_email')

    def full_name(self, obj):
        return str(obj)


class CompanyAdmin(admin.ModelAdmin):
    model = Company
    list_display = ('id', 'company_name', 'company_identifier', 'type', 'status')
    list_filter = ('status',)
    search_fields = ['company_name', 'company_identifier']


class ServiceTicketAdmin(admin.ModelAdmin):
    model = ServiceTicket
    list_display = ('summary', 'status', 'resources', 'record_type',)
    list_filter = ('status', 'record_type',)
    search_fields = ['id', 'summary', 'members__user__username', ]

    def resources(self, obj):
        return ', '.join([str(m) for m in obj.members.all()])

admin.site.register(ConnectWiseBoard, ConnectWiseBoardAdmin)
admin.site.register(TicketStatus, TicketStatusAdmin)
admin.site.register(Member, MemberAdmin)
admin.site.register(ServiceTicket, ServiceTicketAdmin)
admin.site.register(Company, CompanyAdmin)
