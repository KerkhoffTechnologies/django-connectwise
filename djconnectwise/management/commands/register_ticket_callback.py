from django.core.management.base import BaseCommand
from djconnectwise.callback import CallBackHandler


class Command(BaseCommand):
    help = 'Registers the ticket callback with the target connectwise system.'

    def handle(self, *args, **options):
        handler = CallBackHandler()

        print('Created task callback for url: {0}'.format(
            handler.create_ticket_callback()))
