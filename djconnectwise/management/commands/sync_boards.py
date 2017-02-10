from django.core.management.base import BaseCommand
from djconnectwise.sync import BoardSynchronizer


class Command(BaseCommand):
    help = 'Synchronize local board data with connectwise server'

    def handle(self, *args, **options):
        synchronizer = BoardSynchronizer()

        created_count, updated_count = synchronizer.sync()
        msg = 'Synced Boards - Created: {} , Updated: {}'
        self.stdout.write(msg.format(created_count, updated_count))
