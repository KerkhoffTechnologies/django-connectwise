from django.apps import AppConfig


class DjangoConnectwiseConfig(AppConfig):
    name = 'djconnectwise'
    # Django 6.0 changed the global DEFAULT_AUTO_FIELD default from AutoField
    # to BigAutoField. Pin it here so this app's primary keys don't silently
    # depend on the host project's setting; without it, upgrading projects
    # would be prompted to generate an AlterField migration for every model.
    default_auto_field = 'django.db.models.AutoField'
