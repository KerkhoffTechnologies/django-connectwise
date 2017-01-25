from .models import ServiceTicket
from rest_framework import serializers


class ServiceTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceTicket
        fields = ('status',)
