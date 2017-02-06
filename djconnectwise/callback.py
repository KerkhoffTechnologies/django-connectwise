from djconnectwise.api import SystemAPIClient
from djconnectwise.models import CallBackEntry

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse


class CallBackHandler(object):

    def __init__(self, *args, **kwargs):
        self.system_client = SystemAPIClient()

    def create_ticket_callback(self):
        """
        Registers the ticket callback with the target connectwise system.
        Creates and returns a local CallBackEntry instance.
        """

        # removing existing local entries
        CallBackEntry.objects.filter(
            callback_type=CallBackEntry.CALLBACK_TYPES.ticket
        ).delete()

        url = '%s://%s%s%s' % (
            settings.SITE_PROTOCOL,
            Site.objects.get_current().domain,
            reverse('djconnectwise:service-ticket-callback'),
            '?id='
        )

        params = {
            'url': url,
            'objectId': 1,
            'type': CallBackEntry.CALLBACK_TYPES.ticket,
            'level': 'owner'
        }

        entry_json = self.system_client.create_callback(params)

        if entry_json:
            entry = CallBackEntry.objects.create(
                url=entry_json['url'],
                object_id=entry_json['objectId'],
                level=entry_json['level'],
                entry_id=entry_json['id'],
                member_id=entry_json['memberId'],
                callback_type=entry_json['type'],
                enabled=True
            )

            return entry

    def list_callbacks(self):
        """
        Returns a list of dict callback entries that are registered
        with the target system.
        """
        return self.system_client.get_callbacks()

    def remove_ticket_callback(self):
        """
        Removes the ticket callback from connectwise
        and removes the local record
        """
        entry_qset = CallBackEntry.objects.filter(
            callback_type=CallBackEntry.CALLBACK_TYPES.ticket
        )

        if entry_qset.exists():
            entry = entry_qset.last()
            entry.delete()
            return self.system_client.delete_callback(entry.entry_id)
