import pprint

from django.core.management.base import BaseCommand
from djconnectwise.callback import CallBackHandler


class Command(BaseCommand):
    help = 'Lists existing callbacks on target connectwise system.'

    def handle(self, *args, **options):
        handler = CallBackHandler()
        self.stdout.write('Callback List')
        self.stdout.write('-----------------------------------------')

        for c in handler.list():
            pprint.pprint(c)
            self.stdout.write('-----------------------------------------')
