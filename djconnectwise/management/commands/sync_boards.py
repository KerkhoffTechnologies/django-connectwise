from django.core.management.base import BaseCommand
from djconnectwise.api import ServiceAPIClient


class Command(BaseCommand):
    help = 'Synchronize local board and status data with connectwise server'

    def handle(self, *args, **options):
        client = ServiceAPIClient()
        print(client.get_boards())
     	