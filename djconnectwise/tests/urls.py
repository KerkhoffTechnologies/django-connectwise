from django.urls import re_path, include

urlpatterns = [
    re_path(
        r'^callback/',
        include('djconnectwise.urls', namespace='djconnectwise')
    ),
]
