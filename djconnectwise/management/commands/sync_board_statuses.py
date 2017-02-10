from django.core.management.base import BaseCommand
from djconnectwise.sync import BoardStatusSynchronizer


class Command(BaseCommand):
    help = 'Synchronize local board data with connectwise server'

    def handle(self, *args, **options):
        synchronizer = BoardStatusSynchronizer()

        created_count, updated_count = synchronizer.sync()
        msg = 'Synced Board Statuses - Created: {} , Updated: {}'
        self.stdout.write(msg.format(created_count, updated_count))
