# -*- coding: utf-8 -*-
import json
import logging

from braces import views
from djconnectwise.sync import ServiceTicketSynchronizer

from django.http import HttpResponse
from django.views.generic import View

from .models import ServiceTicket

logger = logging.getLogger('kanban')


class ConnectWiseCallBackView(views.CsrfExemptMixin,
                              views.JsonRequestResponseMixin, View):
    def __init__(self, *args, **kwargs):
        super(ConnectWiseCallBackView, self).__init__(*args, **kwargs)
        self.synchronizer = ServiceTicketSynchronizer()


class ServiceTicketCallBackView(ConnectWiseCallBackView):

    def post(self, request, *args, **kwargs):
        post_body = json.loads(request.body)
        action = post_body.get('Action')
        ticket_id = post_body.get('ID')

        logger.debug('{}: {}'.format(action.upper(), post_body))

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
