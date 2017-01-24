# -*- coding: utf-8 -*-
class ConnectWiseCallBackView(views.CsrfExemptMixin, views.JsonRequestResponseMixin, View):
    def __init__(self, *args, **kwargs):
        super(ConnectWiseCallBackView, self).__init__(*args, **kwargs)
        self.synchronizer = ServiceTicketSynchronizer()


class ServiceTicketCallBackView(ConnectWiseCallBackView):
    def post(self, request, *args, **kwargs):
        post_body = json.loads(request.body)
        action = post_body.get('Action')
        ticket_id = post_body.get('ID')
        log.debug('%s: %s' % (action.upper(), post_body))

        if action == 'deleted':
            log.info('Ticket Deleted CallBack: %d' % ticket_id)
            ServiceTicket.objects.filter(id=ticket_id).delete()
        else:
            log.info('Ticket Pre-Update: %d' % ticket_id)
            service_ticket = self.synchronizer \
                .service_client \
                .get_ticket(ticket_id)

            if service_ticket:
                log.info('Ticket Updated CallBack: %d' % ticket_id)
                local_service_ticket = self.synchronizer.sync_ticket(
                    service_ticket,
                    ServiceProvider.objects.all().first()
                )

        # we need not return anything to connectwise
        return HttpResponse('')
