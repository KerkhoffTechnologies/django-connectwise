from django.core.management.base import BaseCommand, CommandError
from djconnectwise.callback import TicketCallBackHandler
from djconnectwise.api import ConnectWiseAPIError

from django.utils.translation import ugettext_lazy as _


class Command(BaseCommand):
    help = str(_('Lists existing callbacks on target ConnectWise system.'))

    def handle(self, *args, **options):
        handler = TicketCallBackHandler()
        self.stdout.write('Callback List')
        self.stdout.write('-----------------------------------------')

        try:
            callbacks = handler.get_callbacks()
        except ConnectWiseAPIError as e:
            raise CommandError(e)

        for c in callbacks:
            self.stdout.write('ID: {}'.format(c['id']))
            self.stdout.write('URL: {}'.format(c['url']))
            self.stdout.write('DESCRIPTION: {}'.format(
                c.get('description', ''))
            )
            self.stdout.write('TYPE: {}'.format(c['type']))
            self.stdout.write('-----------------------------------------')
