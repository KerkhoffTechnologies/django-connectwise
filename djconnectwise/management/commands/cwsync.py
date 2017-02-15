from collections import OrderedDict

from djconnectwise import sync

from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import ugettext_lazy as _

OPTION_NAME = 'connectwise_object'


class Command(BaseCommand):
    help = _('Synchronize the specified object with the Connectwise API')

    synchronizer_map = OrderedDict(
        board=(sync.BoardSynchronizer, _('Board')),
        board_status=(sync.BoardStatusSynchronizer, _('Board Status')),
        company=(sync.CompanySynchronizer, _('Company')),
        member=(sync.MemberSynchronizer, _('Member')),
        ticket=(sync.ServiceTicketSynchronizer, _('Ticket'))
    )

    def add_arguments(self, parser):
        parser.add_argument(OPTION_NAME, nargs='?', type=str)
        parser.add_argument('--reset',
                            action='store_true',
                            dest='reset',
                            default=False)

    def sync_by_class(self, sync_class, obj_name, reset=False):
        synchronizer = sync_class()

        if reset and sync_class == sync.ServiceTicketSynchronizer:
            synchronizer = sync_class(reset=reset)

        created_count, updated_count, deleted_count = synchronizer.sync()
        msg = _('{} Sync Summary - Created: {} , Updated: {}')
        fmt_msg = msg.format(obj_name, created_count, updated_count)

        self.stdout.write(fmt_msg)

    def handle(self, *args, **options):
        sync_classes = []
        connectwise_object_arg = options[OPTION_NAME]
        reset_option = options.get('reset', False)

        if connectwise_object_arg:
            object_arg = connectwise_object_arg
            sync_tuple = self.synchronizer_map.get(object_arg)

            if sync_tuple:
                sync_classes.append(sync_tuple)
            else:
                msg = _('Invalid CW object, choose one of the following: \n{}')
                options_txt = ', '.join(self.synchronizer_map.keys())
                msg = msg.format(options_txt)
                raise CommandError(msg)
        else:
            sync_classes = self.synchronizer_map.values()

        for sync_class, obj_name in sync_classes:
            self.sync_by_class(sync_class, obj_name, reset=reset_option)