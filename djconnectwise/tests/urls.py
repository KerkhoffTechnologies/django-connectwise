from django.conf.urls import url, include

urlpatterns = [
    url(r'^callback/', include(
        'djconnectwise.urls', namespace='djconnectwise')
        ),
]
