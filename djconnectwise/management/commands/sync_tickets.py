from django.core.management.base import BaseCommand
from djconnectwise.sync import ServiceTicketSynchronizer


class Command(BaseCommand):
    help = 'Executes the ServiceTicket Synchronizer.'

    def add_arguments(self, parser):
        parser.add_argument('--reset',
            action='store_true',
            dest='reset',
            default=False,
            help='Refresh all tickets and refresh assignments from connectwise')

    def handle(self, *args, **options):
        if options['reset']:
            synchronizer = ServiceTicketSynchronizer(True)
        else:
            synchronizer = ServiceTicketSynchronizer()
        created_count, updated_count, delete_count = synchronizer.start()
        print('Number of tickets created: %d'%created_count)
        print('Number of tickets updated: %d'%updated_count)
        print('Number of tickets deleted: %d'%delete_count)
