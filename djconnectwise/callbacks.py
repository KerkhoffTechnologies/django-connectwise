import logging
from djconnectwise.api import SystemAPIClient
from djconnectwise.utils import DjconnectwiseSettings


logger = logging.getLogger(__name__)
# We need to have exactly these callbacks. Fields that are omitted are not
# considered. (URL is set at runtime.)
# See https://developer.connectwise.com/Products/Manage/Developer_Guide#Callbacks_(Webhooks)  # noqa
NEEDED_CALLBACKS = [
  {
    "type": "ticket",
    "description": "Kanban application ticket callback",
    "url": None,
    "objectId": 1,
    "level": "owner",
  },
  {
    "type": "project",
    "description": "Kanban application project callback",
    "url": None,
    "objectId": 1,
    "level": "owner",
  },
  {
    "type": "company",
    "description": "Kanban application company callback",
    "url": None,
    "objectId": 1,
    "level": "owner",
  },
  {
    "type": "contact",
    "description": "Kanban application contact callback",
    "url": None,
    "objectId": 1,
    "level": "owner",
  },
  {
    "type": "opportunity",
    "description": "Kanban application opportunity callback",
    "url": None,
    "objectId": 1,
    "level": "owner",
  },
  {
    "type": "activity",
    "description": "Kanban application activity callback",
    "url": None,
    "objectId": 1,
    "level": "owner",
  },
  {
    "type": "schedule",
    "description": "Kanban application schedule entry callback",
    "url": None,
    "objectId": 1,
    "level": "owner",
  }
]


class CallbacksHandler:
    def __init__(self):
        super().__init__()
        self.system_client = SystemAPIClient()
        self.settings = DjconnectwiseSettings().get_settings()

    def get_callbacks(self):
        results = []
        page = 1
        while True:
            page_records = self.system_client.get_callbacks(
                page=page,
                page_size=self.settings['batch_size'],
                conditions=[
                    'url contains "{}"'.format(self.settings['callback_host'])
                ]
            )
            results += page_records
            page += 1
            if len(page_records) < self.settings['batch_size']:
                # This page wasn't full, so there's no more records after
                # this page.
                break
        return results

    def get_needed_callbacks(self):
        """
        Return a list of callbacks
        """
        result = NEEDED_CALLBACKS.copy()
        for cb in result:
            cb['url'] = '{}{}'.format(
                self.settings['callback_host'],
                self.settings['callback_url']
            )
        return result

    def _calculate_missing_unneeded_callbacks(self,
                                              needed_callbacks,
                                              current_callbacks):
        """
        Given the list of needed callbacks and current callbacks, figure out
        which callbacks need to be registered and which ones need to be
        removed.

        Returns a tuple of (need-to-add, need-to-remove) callbacks.
        """
        # For each current callback that matches a needed callback, delete it
        # from both needed and current.
        current_indexes_delete = set()
        needed_indexes_delete = set()
        field_names = ['type', 'description', 'url', 'objectId', 'level']
        # Add the index of the element to delete to a list, because it's
        # an error to delete elements out of a list while iterating through.
        for i_cur, current in enumerate(current_callbacks):
            for i_need, needed in enumerate(needed_callbacks):
                all_matched = True
                for field in field_names:
                    if current[field] != needed[field]:
                        # If any field doesn't match, don't delete the cb
                        all_matched = False
                if all_matched:
                    current_indexes_delete.add(i_cur)
                    needed_indexes_delete.add(i_need)
        for i_cur in reversed(sorted(current_indexes_delete)):
            # Delete from the end
            current_callbacks.pop(i_cur)
        for i_need in reversed(sorted(needed_indexes_delete)):
            # Delete from the end
            needed_callbacks.pop(i_need)

        return needed_callbacks, current_callbacks

    def ensure_registered(self):
        """
        Do the minimum changes to ensure our callbacks are registered
        exactly once.
        """
        needed_callbacks = self.get_needed_callbacks()
        current_callbacks = self.get_callbacks()
        callbacks_to_add, callbacks_to_remove = \
            self._calculate_missing_unneeded_callbacks(
                needed_callbacks, current_callbacks
            )

        for callback in callbacks_to_add:
            self._register_callback(callback)
        for callback in callbacks_to_remove:
            self._delete_callback(callback)

    def ensure_deleted(self):
        """Do the needful to ensure our callbacks are gone."""
        callbacks = self.get_callbacks()
        for callback in callbacks:
            self._delete_callback(callback)

    def _register_callback(self, callback):
        logger.info('Registering {} callback'.format(callback['type']))
        self.system_client.create_callback(callback)

    def _delete_callback(self, callback):
        logger.info('Deleting callback {}'.format(callback['id']))
        self.system_client.delete_callback(callback['id'])
