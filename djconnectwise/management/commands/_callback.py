from django.core.management.base import BaseCommand, CommandError
from djconnectwise import callback

from collections import OrderedDict

from django.utils.translation import ugettext_lazy as _


OPTION_NAME = 'callback'


class Command(BaseCommand):
    help = _('Registers the callback with the target connectwise system.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        handlers = (
            ('ticket', callback.TicketCallBackHandler),
            ('project', callback.ProjectCallBackHandler),
            ('company', callback.CompanyCallBackHandler),
        )
        self.handler_map = OrderedDict()
        for name, handler in handlers:
            self.handler_map[name] = handler

    def add_arguments(self, parser):
        parser.add_argument(OPTION_NAME, nargs='+', type=str)

    def handle(self, *args, **options):
        obj_name = options[OPTION_NAME][0]
        handler_class = self.handler_map.get(obj_name)

        if handler_class:

            if self.ACTION == 'create':
                handler_class().create()
            else:
                handler_class().delete()

            self.stdout.write('{} {} callback'.format(
                self.ACTION, obj_name))
        else:
            msg = _('Invalid Callback, choose one of the following: \n{}')
            options_txt = ', '.join(self.handler_map.keys())
            msg = msg.format(options_txt)
            raise CommandError(msg)
