from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import ugettext_lazy as _
from datetime import datetime, timedelta
import logging

from djconnectwise.models import SyncJob

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = _('Remove old sync job entries. Defaults to 4 weeks, but ' +
             'the cutoff date can be customized by combining the days and ' +
             'minutes options.')

    def add_arguments(self, parser):
        parser.add_argument('--days',
                            nargs='?',
                            type=int,
                            default=28,
                            help='previous number of days of sync job logs to keep',
                            )
        parser.add_argument('--minutes',
                            nargs='?',
                            type=int,
                            default=0,
                            help='number of minutes of sync job logs to keep',
                            )

    def handle(self, *args, **options):
        days_option = options.get('days', 28)
        minutes_option = options.get('minutes', 0)

        cutoff_date = datetime.now() - timedelta(days=days_option,
                                                 minutes=minutes_option)
        old_entries = SyncJob.objects.exclude(start_time__gt=cutoff_date)
        count = old_entries.count()

        if count == 0:
            msg = 'There are no sync job entries older than {}'
            logger.info(msg.format(
                cutoff_date.isoformat(' '))
            )
        else:
            try:
                old_entries.delete()

                msg = '{} sync jobs older than {} were deleted'
                logger.info(msg.format(
                    count, cutoff_date.isoformat(' '))
                )
            except CommandError as e:
                logger.error(e)
