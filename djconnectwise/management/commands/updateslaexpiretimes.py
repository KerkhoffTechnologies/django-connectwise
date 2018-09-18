from django.core.management.base import BaseCommand
from django.utils import timezone
from djconnectwise.models import Ticket
import datetime
import random

MIN_DATE = -2  # Earliest date, days prior to today
MAX_DATE = 12  # Latest date, days prior to today
NOW = timezone.now()

class Command(BaseCommand):
    help = 'Update the sla expire date on tickets to dates close to current ' \
           'date, past and future.'

    @staticmethod
    def get_random_date():
        min_sec = MIN_DATE * 86400
        max_sec = MAX_DATE * 86400
        # ~%13 of tickets will have expired SLA on average.
        # This may need some tweaking if it feels like too many or too few.
        difference = random.randint(min_sec, max_sec)
        return NOW + datetime.timedelta(seconds=difference)

    def handle(self, *args, **kwargs):
        for ticket in Ticket.objects.all():
            if ticket.sla_stage == "Resolved" or ticket.sla_stage == "Waiting":
                continue
            ticket.sla_expire_date = self.get_random_date()
            ticket.save()
