# -*- coding: utf-8 -*-
import json
import logging

from braces import views
from djconnectwise import sync

from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.views.generic import View

from . import models


logger = logging.getLogger(__name__)


class ConnectWiseCallBackView(views.CsrfExemptMixin,
                              views.JsonRequestResponseMixin, View):
    sync_class = None

    def __init__(self, *args, **kwargs):
        super(ConnectWiseCallBackView, self).__init__(*args, **kwargs)
        self.synchronizer = self.sync_class()

    def post(self, request, *args, **kwargs):
        body = json.loads(request.body.decode(encoding='utf-8'))
        action = request.GET.get('action')

        if action is None:
            msg = 'Received callback with no action parameter.'
            logger.warning(msg)

            err = "The 'action' parameter is required."
            return HttpResponseBadRequest(err)
        object_id = request.GET.get('id')

        if object_id is None:
            msg = 'Received {} callback with no object_id parameter.'
            logger.warning(msg.format(action))

            err = "The 'object_id' parameter is required."
            return HttpResponseBadRequest(err)

        logger.debug('{} {}: {}'.format(action.upper(), object_id, body))

        if action == 'deleted':
            self.delete(object_id)
        else:
            self.update(object_id)

        # we need not return anything to connectwise
        return HttpResponse(status=204)

    def update(self, object_id):
        self.model_class.objects.filter(id=object_id)
        logger.info('{} Deleted CallBack: {}'.format(object_id))

    def delete(self, object_id):
        self.model_class.objects.filter(id=object_id).delete()
        logger.info('{} Deleted CallBack: {}'.format(object_id))


class TicketCallBackView(ConnectWiseCallBackView):
    sync_class = sync.TicketSynchronizer
    model_class = sync_class

    def update(self, object_id):
        model_name = self.model_class.__name__
        logger.info('{} Pre-Update: {}'.format(model_name, object_id))

        ticket = self.synchronizer \
            .service_client \
            .get_ticket(object_id)

        if ticket:
            msg = '{} Updated CallBack: {}'
            logger.info(msg.format(model_name, object_id))
            self.synchronizer.sync_ticket(ticket)
