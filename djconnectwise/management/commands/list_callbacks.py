from django.core.management.base import BaseCommand
from djconnectwise.callback import TicketCallBackHandler


class Command(BaseCommand):
    help = 'Lists existing callbacks on target connectwise system.'

    def handle(self, *args, **options):
        handler = TicketCallBackHandler()
        self.stdout.write('Callback List')
        self.stdout.write('-----------------------------------------')

        for c in handler.get_callbacks():

            self.stdout.write('ID:{}'.format(c['id']))
            self.stdout.write('DESCRIPTION: {}'.format(c['description']))
            self.stdout.write('TYPE:'.format(c['type']))
            self.stdout.write('-----------------------------------------')
