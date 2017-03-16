# -*- coding: utf-8 -*-
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


CALLBACK_DELETED = 'deleted'
CALLBACK_UPDATED = 'updated'

CALLBACK_ACTIONS = (
    (CALLBACK_DELETED, CALLBACK_DELETED),
    (CALLBACK_UPDATED, CALLBACK_UPDATED)
)


class CallBackView(views.CsrfExemptMixin,
                   views.JsonRequestResponseMixin, View):

    CALLBACK_TYPES = {
        models.CallBackEntry.TICKET: (
            sync.TicketSynchronizer, models.Ticket
        ),
        models.CallBackEntry.PROJECT: (
            sync.ProjectSynchronizer, models.Project
        ),
        models.CallBackEntry.COMPANY: (
            sync.CompanySynchronizer, models.Company
        ),
    }

    def post(self, request, *args, **kwargs):
        """
        Update or delete entity by fetching it from CW again. We mostly
        ignore the JSON that CW sends to us, because their method of
        verifying the request requires us to make a request back to them for
        a signing key, so we may as well just make a request for the whole
        object.

        ConnectWise docs for callback verification:
        https://developer.connectwise.com/Manage/Developer_Guide#Verifying_the_Callback_Source
        """
        body = json.loads(request.body.decode(encoding='utf-8'))
        required_fields = {
            'action': body['Action'],
            'entity': body['Entity'],
            'callback_type': body['Type']
        }
        form = CallBackForm(required_fields)

        if not form.is_valid():
            fields = ', '.join(form.errors.keys())
            msg = 'Received callback with missing parameters: {}.'.format(
                fields)
            logger.warning(msg)
            return HttpResponseBadRequest(json.dumps(form.errors))

        self.action = form.cleaned_data['action']
        self.callback_type = body.get('Type')
        sync_class, self.model_class = \
            self.CALLBACK_TYPES[self.callback_type]
        self.synchronizer = sync_class()
        entity = json.loads(body.get('Entity'))

        logger.debug('Callback {} {}: {}'.format(
            self.action.upper(), entity, body)
        )

        if self.action == CALLBACK_DELETED:
            self.delete(entity)
        else:
            self.update(entity)

        # We need not return anything to ConnectWise
        return HttpResponse(status=204)

    def update(self, entity):
        entity_id = entity['id']
        try:
            self.synchronizer.fetch_sync_by_id(entity_id)
        except ConnectWiseAPIError as e:
            # Something bad happened when talking to the API. There's not
            # much we can do, so just log it. We should get synced back up
            # when the next periodic sync job runs.
            logger.error(
                'API call failed in model {} ID {} callback: '
                '{}'.format(self.model_class, entity_id, e)
            )

    def delete(self, entity):
        entity_id = entity['id']
        self.model_class.objects.filter(id=entity['id']).delete()
        logger.info('Deleted via CallBack: {}'.format(entity['id']))


class CallBackForm(forms.Form):
    entity = forms.CharField()
    action = forms.ChoiceField(choices=CALLBACK_ACTIONS)

    callback_type = forms.ChoiceField(
        choices=[(c, c) for c in CallBackView.CALLBACK_TYPES.keys()]
    )
