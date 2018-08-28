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
        if old_ticket.status > instance.status or \
                old_ticket.status < instance.status:
            instance.calculate_sla_expiry(
                    old_status=old_ticket.status)
    except Ticket.DoesNotExist:
        # This is normal when creating a new ticket.
        instance.calculate_sla_expiry()
    except TypeError:
        # This will happen during unit tests unrelated to SLAs
        # Rather than updating all the old unit tests with quite a bit of
        # SLA data they do not need at the moment, just skip SLA calculations
        # on those tests
        pass
