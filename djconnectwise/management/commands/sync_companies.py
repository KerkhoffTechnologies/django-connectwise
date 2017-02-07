from django.core.management.base import BaseCommand
from djconnectwise.sync import CompanySynchronizer


class Command(BaseCommand):
    help = 'Synchronize local company data with connectwise server'

    def handle(self, *args, **options):
        synchronizer = CompanySynchronizer()

        _, _, msg = synchronizer.sync_companies()
        self.stdout.write(msg)
        return msg
