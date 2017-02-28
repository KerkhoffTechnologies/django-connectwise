# -*- coding: utf-8 -*-
from django.conf.urls import url, patterns, include
from . import views

urlpatterns = [
    url(
        regex=r'^callback/$',
        view=views.CallBackView.as_view(),
        name='callback'
    ),
]

included = include(urlpatterns, namespace="djconnectwise")
urlpatterns = patterns('', url(r'^/', included),)
