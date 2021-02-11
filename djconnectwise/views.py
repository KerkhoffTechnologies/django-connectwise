import json
import logging

from braces import views

from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django import forms
from django.views.generic import View

from . import models
from djconnectwise import sync
from .api import ConnectWiseAPIError


logger = logging.getLogger(__name__)


CALLBACK_ADDED = 'added'
CALLBACK_UPDATED = 'updated'
CALLBACK_DELETED = 'deleted'

CALLBACK_ACTIONS = (
    (CALLBACK_ADDED, CALLBACK_ADDED),
    (CALLBACK_UPDATED, CALLBACK_UPDATED),
    (CALLBACK_DELETED, CALLBACK_DELETED),
)


def get_ticket_sync_class(entity):
    project_ticket_types = [
        models.Ticket.PROJECT_TICKET, models.Ticket.PROJECT_ISSUE
    ]
    if entity:
        ticket_entity = json.loads(entity)
        record_type = ticket_entity.get('recordType')
    else:
        record_type = None

    if record_type in project_ticket_types:
        sync_class = sync.ProjectTicketSynchronizer
    else:
        sync_class = sync.ServiceTicketSynchronizer

    return sync_class


class CallBackView(views.CsrfExemptMixin,
                   views.JsonRequestResponseMixin, View):

    CALLBACK_TICKET_TYPE = 'ticket'
    CALLBACK_TYPES = {
        'ticket': (
            get_ticket_sync_class, models.Ticket
        ),
        'project': (
            sync.ProjectSynchronizer, models.Project
        ),
        'company': (
            sync.CompanySynchronizer, models.Company
        ),
        'contact': (
            sync.ContactSynchronizer, models.Contact
        ),
        'opportunity': (
            sync.OpportunitySynchronizer, models.Opportunity
        ),
        'activity': (
            sync.ActivitySynchronizer, models.Activity
        ),
        'schedule': (
            sync.ScheduleEntriesSynchronizer, models.ScheduleEntry
        ),
    }

    def post(self, request, *args, **kwargs):
        """
        Add, update or delete entity by fetching it from CW again. We mostly
        ignore the JSON that CW sends to us, because their method of
        verifying the request requires us to make a request back to them for
        a signing key, so we may as well just make a request for the whole
        object.

        ConnectWise docs for callback verification:
        https://developer.connectwise.com/Manage/Developer_Guide#Verifying_the_Callback_Source
        """
        body = json.loads(
            request.body.decode(encoding='utf-8', errors='replace')
        )
        logger.debug('Callback {}: {}'.format(
            request.META['QUERY_STRING'], body)
        )

        fields = {
            'entity_id': body['ID'],
            'action': body['Action'],
            'callback_type': body['Type']
        }
        form = CallBackForm(fields)

        if not form.is_valid():
            fields = ', '.join(form.errors.keys())
            msg = 'Received callback with missing parameters: {}.'.format(
                fields)
            logger.warning(msg)
            return HttpResponseBadRequest(json.dumps(form.errors))

        entity_id = form.cleaned_data['entity_id']
        action = form.cleaned_data['action']
        callback_type = body.get('Type')

        if callback_type == self.CALLBACK_TICKET_TYPE:
            entity = body.get('Entity')
            get_synchronizer, model_class = \
                self.CALLBACK_TYPES[callback_type]

            sync_class = get_synchronizer(entity)
        else:
            sync_class, model_class = self.CALLBACK_TYPES[callback_type]

        synchronizer = sync_class()

        try:
            self.handle(entity_id, action, callback_type, synchronizer)
        except ConnectWiseAPIError as e:
            # Something bad happened when talking to the API. There's not
            # much we can do, so just log it. We should get synced back up
            # when the next periodic sync job runs.
            logger.error(
                'API call failed in model {} ID {} callback: '
                '{}'.format(model_class, entity_id, e)
            )

        # We need not return anything to ConnectWise
        return HttpResponse(status=204)

    def handle(self, entity_id, action, callback_type, synchronizer):
        """
        Do the interesting stuff here, so that it can be overridden in
        a child class if needed.
        """
        if action == CALLBACK_DELETED:
            synchronizer.fetch_delete_by_id(entity_id)
        else:
            synchronizer.fetch_sync_by_id(entity_id)


class CallBackForm(forms.Form):
    entity_id = forms.IntegerField()
    action = forms.ChoiceField(choices=CALLBACK_ACTIONS)
    callback_type = forms.ChoiceField(
        choices=[(c, c) for c in CallBackView.CALLBACK_TYPES.keys()]
    )
