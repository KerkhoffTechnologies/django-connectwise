# -*- coding: utf-8 -*-
import json
import logging

from braces import views
from djconnectwise.sync import ServiceTicketSynchronizer

from django.http import HttpResponse, HttpResponseBadRequest
from django.views.generic import View

from .models import ServiceTicket


logger = logging.getLogger(__name__)


class ConnectWiseCallBackView(views.CsrfExemptMixin,
                              views.JsonRequestResponseMixin, View):
    def __init__(self, *args, **kwargs):
        super(ConnectWiseCallBackView, self).__init__(*args, **kwargs)
        self.synchronizer = ServiceTicketSynchronizer()


class ServiceTicketCallBackView(ConnectWiseCallBackView):

    def get(self, request, *args, **kwargs):
        body = json.loads(request.body)
        action = request.GET.get('action')
        if action is None:
            logger.warning('Received ticket callback with no action parameter.')
            return HttpResponseBadRequest("The 'action' parameter is required.")
        ticket_id = request.GET.get('id')
        if ticket_id is None:
            logger.warning('Received ticket callback with no ticket_id parameter.')
            return HttpResponseBadRequest("The 'ticket_id' parameter is required.")

        logger.debug('{} {}: {}'.format(action.upper(), ticket_id, body))

        if action == 'deleted':
            logger.info('Ticket Deleted CallBack: {}'.format(ticket_id))
            ServiceTicket.objects.filter(id=ticket_id).delete()
        else:
            logger.info('Ticket Pre-Update: {}'.format(ticket_id))
            service_ticket = self.synchronizer \
                .service_client \
                .get_ticket(ticket_id)

            if service_ticket:
                logger.info('Ticket Updated CallBack: {}'.format(ticket_id))
                self.synchronizer.sync_ticket(service_ticket)

        # we need not return anything to connectwise
        return HttpResponse(status=204)
