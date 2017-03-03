from django.conf.urls import url
from . import views

urlpatterns = [
    url(
        regex=r'^callback/$',
        view=views.CallBackView.as_view(),
        name='callback'
    ),
]
