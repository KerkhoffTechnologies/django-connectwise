from django.core.management.base import BaseCommand
from djconnectwise.sync import ServiceTicketSynchronizer


class Command(BaseCommand):
    help = 'Executes the ServiceTicket Synchronizer.'

    def add_arguments(self, parser):
        hlp_msg = 'Refresh tickets and assignments from ConnectWise'
        parser.add_argument('--reset',
                            action='store_true',
                            dest='reset',
                            default=False,
                            help=hlp_msg)

    def handle(self, *args, **options):
        synchronizer = ServiceTicketSynchronizer(reset=options['reset'])
        created_count, updated_count, delete_count = synchronizer.start()

        self.stdout.write('Number of tickets created: %d' % created_count)
        self.stdout.write('Number of tickets updated: %d' % updated_count)
        self.stdout.write('Number of tickets deleted: %d' % delete_count)
