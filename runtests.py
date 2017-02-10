#!/usr/bin/env python
from django.conf import settings
from django.core.management import call_command
from django.test.utils import get_runner
import django


settings.configure(
    DEBUG=True,
    INSTALLED_APPS=(
        'djconnectwise',
        'easy_thumbnails',
    ),
    CONNECTWISE_SERVER_URL='https://localhost',
    CONNECTWISE_CREDENTIALS={
        'company_id': 'training',
        'integrator_login_id': '',
        'integrator_password': '',
        'api_public_key': '',
        'api_private_key': '',
        'api_codebase': 'v4_6_release',
    },
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': 'djconnectwise-test.sqlite',
        },
    },
    USE_TZ=True,  # Prevent 'ValueError: SQLite backend does not support
    # timezone-aware datetimes when USE_TZ is False.'
    DJCONNECTWISE_COMPANY_ALIAS=False,
)


def _setup():
    """Configure Django stuff for tests."""
    django.setup()
    # Set up the test DB, if necessary
    call_command('migrate', 'djconnectwise')
    # Clear out the test DB
    call_command('flush', '--noinput')


def suite():
    """
    Set up and return a test suite. This is used in `python setup.py test`.
    """
    _setup()
    runner_cls = get_runner(settings)
    return runner_cls().build_suite(test_labels=None)


if __name__ == '__main__':
    _setup()
    call_command('test')
