from django.apps import AppConfig


class DjangoConnectwiseConfig(AppConfig):
    name = 'djconnectwise'

    def ready(self):
        # Register signal handlers using decorators.
        from djconnectwise import signals
