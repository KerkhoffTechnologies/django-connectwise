from django.urls import re_path
from . import views

app_name = 'djconnectwise'

urlpatterns = [
    re_path(
        r'^callback/$',
        view=views.CallBackView.as_view(),
        name='callback'
    ),
]
