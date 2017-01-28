from django.core.management.base import BaseCommand
from djconnectwise.sync import ServiceTicketSynchronizer


class Command(BaseCommand):
    help = 'Executes the ServiceTicket Synchronizer.'

    def add_arguments(self, parser):
        hlp_msg = 'Refresh tickets and refresh assignments from connectwise'
        parser.add_argument('--reset',
                            action='store_true',
                            dest='reset',
                            default=False,
                            help=hlp_msg)

    def handle(self, *args, **options):
        synchronizer = ServiceTicketSynchronizer(
            options['reset'] is not None)

        created_count, updated_count, delete_count = synchronizer.start()

        print('Number of tickets created: %d' % created_count)
        print('Number of tickets updated: %d' % updated_count)
        print('Number of tickets deleted: %d' % delete_count)
