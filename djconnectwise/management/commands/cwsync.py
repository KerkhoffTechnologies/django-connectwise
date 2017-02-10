from djconnectwise import sync

from django.core.management.base import BaseCommand, CommandError

OPTION_NAME = 'connectwise_object'


class Command(BaseCommand):
    help = 'Synchronize the specified object with the Connectwise API'

    synchronizer_map = dict(
        board=sync.BoardSynchronizer,
        company=sync.CompanySynchronizer,
        board_status=sync.BoardStatusSynchronizer
    )

    def add_arguments(self, parser):
        parser.add_argument(OPTION_NAME, nargs='+', type=str)

    def handle(self, *args, **options):
        object_name = options[OPTION_NAME][0]
        synchronizer_class = self.synchronizer_map.get(object_name)

        if synchronizer_class:
            synchronizer = synchronizer_class()
            created_count, updated_count = synchronizer.sync()
            msg = 'Sync Summary - Created: {} , Updated: {}'
            self.stdout.write(msg.format(created_count, updated_count))
        else:
            msg = 'Invalid CW object, choose one of the following: \n\n {}'
            options_txt = ', '.join(self.synchronizer_map.keys())
            msg = msg.format(options_txt)
            raise CommandError(msg)
