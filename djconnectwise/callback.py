import logging

from requests.exceptions import RequestException

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
import django

from djconnectwise.api import SystemAPIClient
from djconnectwise.models import CallBackEntry
from djconnectwise.utils import RequestSettings


logger = logging.getLogger(__name__)


class CallBackHandler:
    CALLBACK_ID = None
    CALLBACK_TYPE = None

    def __init__(self, *args, **kwargs):
        self.system_client = SystemAPIClient()

        request_settings = RequestSettings().get_settings()
        self.batch_size = request_settings['batch_size']

        if not self.CALLBACK_ID:
            raise NotImplementedError('CALLBACK_ID must be assigned a value')

        if not self.CALLBACK_TYPE:
            raise NotImplementedError('CALLBACK_TYPE must be assigned a value')

    def _get_host(self):
        """Return the protocol & hostname."""
        if hasattr(settings, 'DJCONNECTWISE_TEST_DOMAIN'):
            # bypass Sites framework for tests
            host = '{}'.format(
                settings.DJCONNECTWISE_TEST_DOMAIN,
            )
        else:
            host = '{}://{}'.format(
                settings.DJCONNECTWISE_CALLBACK_PROTOCOL,
                Site.objects.get_current().domain,
            )
        return host

    def _get_callback_url(self):
        """Return the full callback URL."""
        if hasattr(settings, 'DJCONNECTWISE_TEST_DOMAIN'):
            # bypass Sites framework for tests
            url = '{}/{}'.format(
                self._get_host(),
                '?id='
            )
        else:
            url = '{}{}{}'.format(
                self._get_host(),
                reverse('djconnectwise:callback'),
                '?id='
            )
        return url

    def _create_callback(self, callback_id, callback_type):
        """
        Registers a callback with the target connectwise system.
        Creates and returns a local CallBackEntry instance.
        """
        params = {
            'url': self._get_callback_url(),
            'objectId': callback_id,
            'type': callback_type,
            'level': 'owner',
            'description': 'Kanban application {} callback'.format(
                callback_type
            )
        }

        entry_json = self.system_client.create_callback(params)

        if entry_json:
            entry = None
            try:
                entry = CallBackEntry.objects.create(
                    id=entry_json['id'],
                    url=entry_json['url'],
                    object_id=entry_json['objectId'],
                    level=entry_json['level'],
                    member_id=entry_json['memberId'],
                    description=entry_json['description'],
                    callback_type=entry_json['type'],
                    inactive_flag=False
                )

            except django.db.utils.Error as e:
                logger.error('CallBackEntry Creation Failed: {}'.format(e))
                self.system_client.delete_callback(entry_json['id'])

            return entry

    def create(self):
        """
        Registers the callback with the target connectwise system.
        Creates and returns a local CallBackEntry instance.
        """
        return self._create_callback(self.CALLBACK_ID,
                                     self.CALLBACK_TYPE)

    def get_callbacks(self):
        """
        Returns a list of dict callback entries that
        are registered with the target system.
        """
        results = []
        page = 1
        while True:
            logger.info(
                'Fetching callback records, batch {}'.format(page)
            )
            page_records = self.system_client.get_callbacks(
                page=page, page_size=self.batch_size,
            )
            results += page_records
            page += 1
            if len(page_records) < self.batch_size:
                # This page wasn't full, so there's no more records after
                # this page.
                break
        return results

    def delete(self):
        """
        Removes the callback from connectwise and
        removes the local record.
        """
        entry_qset = CallBackEntry.objects.filter(
            callback_type=self.CALLBACK_TYPE)

        entries = {e.id: e for e in entry_qset}
        host = self._get_host()
        # Only delete a callback that starts with our expected hostname, so
        # we don't explode an other integration's callbacks.
        api_entries = [
            e for e in self.get_callbacks() if
            e['type'] == self.CALLBACK_TYPE and e['url'].startswith(host)
        ]

        for entry in api_entries:
            entry_id = entry['id']
            try:
                # Only delete the DB entry once CW has
                # accepted our delete request.
                self.system_client.delete_callback(entry_id)
                if entry_id in entries:
                    entries[entry_id].delete()

                logger.info('Deleted callback {}.'.format(entry_id))
            except RequestException as e:
                msg = 'Failed to remove callback: {}: {}'
                logger.warning(msg.format(entry_id, e))


class TicketCallBackHandler(CallBackHandler):
    CALLBACK_ID = 1
    CALLBACK_TYPE = CallBackEntry.CALLBACK_TYPES.ticket


class ProjectCallBackHandler(CallBackHandler):
    CALLBACK_ID = 2
    CALLBACK_TYPE = CallBackEntry.CALLBACK_TYPES.project


class CompanyCallBackHandler(CallBackHandler):
    CALLBACK_ID = 3
    CALLBACK_TYPE = CallBackEntry.CALLBACK_TYPES.company


class OpportunityCallBackHandler(CallBackHandler):
    CALLBACK_ID = 4
    CALLBACK_TYPE = CallBackEntry.CALLBACK_TYPES.opportunity
