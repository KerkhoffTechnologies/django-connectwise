from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import ugettext_lazy as _
from datetime import datetime, timedelta
import logging

from djconnectwise.models import SyncJob

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = str(_('Remove old sync job entries. Defaults to 4 weeks, but \
           the cutoff date can be customized with the "days" option.'))

    def add_arguments(self, parser):
        parser.add_argument('--days',
                            nargs='?',
                            type=int,
                            default=28,
                            help='number of days worth of sync job ' +
                                 'logs to keep', )

    def handle(self, *args, **options):
        days_option = options.get('days', 28)

        verbosity = int(options['verbosity'])
        if verbosity == 1:
            logger.setLevel(logging.WARN)
        elif verbosity == 2:
            logger.setLevel(logging.INFO)

        cutoff_date = datetime.now() - timedelta(days=days_option)
        old_entries = SyncJob.objects.exclude(start_time__gt=cutoff_date)
        count = old_entries.count()

        try:

            old_entries.delete()

        except CommandError as e:
            logger.error(e)
        finally:
            msg = '{} sync jobs older than {} were deleted'
            logger.info(msg.format(
                count, cutoff_date.isoformat(' '))
            )
