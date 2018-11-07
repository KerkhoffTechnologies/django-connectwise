from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import Ticket
import logging


logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Ticket)
def handle_ticket_sla_update_pre_save(sender, instance, **kwargs):
    # Signal for updating a tickets SLA information if necessary
    try:
        old_ticket = Ticket.objects.get(id=instance.id)
        if not old_ticket.status.escalation_status or \
                not instance.status.escalation_status:
            # If there are unit tests running that don't require SLA data
            # or if the instance does not have SLA data, return
            return
        elif old_ticket.status > instance.status or \
                old_ticket.status < instance.status:
            instance.calculate_sla_expiry()
        elif old_ticket.priority != instance.priority:
            instance.calculate_sla_expiry()
    except Ticket.DoesNotExist:
        # This is normal when creating a new ticket.
        instance.calculate_sla_expiry()
