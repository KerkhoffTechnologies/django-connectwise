# -*- coding: utf-8 -*-
from braces import views
from djconnectwise.sync import ServiceTicketSynchronizer
import json
from .models import ServiceTicket
from django.http import HttpResponse
import logging
from django.views.generic import View


logger = logging.getLogger(__name__)


class ConnectWiseCallBackView(views.CsrfExemptMixin, views.JsonRequestResponseMixin, View):
    def __init__(self, *args, **kwargs):
        super(ConnectWiseCallBackView, self).__init__(*args, **kwargs)
        self.synchronizer = ServiceTicketSynchronizer()


class ServiceTicketCallBackView(ConnectWiseCallBackView):
    def post(self, request, *args, **kwargs):
        post_body = json.loads(request.body)
        action = post_body.get('Action')
        ticket_id = post_body.get('ID')
        logger.debug('%s: %s' % (action.upper(), post_body))

        if action == 'deleted':
            logger.info('Ticket Deleted CallBack: %d' % ticket_id)
            ServiceTicket.objects.filter(id=ticket_id).delete()
        else:
            logger.info('Ticket Pre-Update: %d' % ticket_id)
            service_ticket = self.synchronizer \
                .service_client \
                .get_ticket(ticket_id)

            if service_ticket:
                logger.info('Ticket Updated CallBack: %d' % ticket_id)
                local_service_ticket = self.synchronizer.sync_ticket(
                    service_ticket,
                )

        # we need not return anything to connectwise
        return HttpResponse('')
