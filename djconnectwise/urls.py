# -*- coding: utf-8 -*-
from django.conf.urls import url
from . import views

urlpatterns = [
    url(
        regex=r'^ticket/$',
        view=views.TicketCallBackView.as_view(),
        name='service-ticket-callback'
    ),

    url(
        regex=r'^project/$',
        view=views.TicketCallBackView.as_view(),
        name='project-callback'
    ),
]
