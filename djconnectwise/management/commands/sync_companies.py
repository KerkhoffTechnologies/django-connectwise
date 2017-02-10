from django.core.management.base import BaseCommand
from djconnectwise.sync import CompanySynchronizer


class Command(BaseCommand):
    help = 'Synchronize local company data with connectwise server'

    def handle(self, *args, **options):
        synchronizer = CompanySynchronizer()

        created_count, updated_count = synchronizer.sync()
        msg = 'Synced Companies - Created: {} , Updated: {}'
        self.stdout.write(msg.format(created_count, updated_count))
