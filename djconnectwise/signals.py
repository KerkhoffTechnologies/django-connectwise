from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from djconnectwise.models import Ticket

from django.utils import timezone
import logging

@receiver(pre_save, sender=Ticket)
def handle_ticket_pre_save(sender, instance, **kwargs):


    try:
        logger.info(
            'Huzzah'
        )
    except ConnectWiseServiceRank.DoesNotExist:
        # This is normal when creating a new ticket.
        pass
