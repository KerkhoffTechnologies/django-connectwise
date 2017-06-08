#!/usr/bin/env python
import subprocess
import sys

from django.conf import settings
from django.core.management import call_command
from django.test.utils import get_runner
import django
import tempfile

DEBUG = True
tmp_media = tempfile.TemporaryDirectory()

settings.configure(
    DEBUG=True,
    INSTALLED_APPS=(  # Including django.contrib apps prevents warnings during
        # tests.
        'djconnectwise',
        'easy_thumbnails',
        'django.contrib.contenttypes',
        'django.contrib.auth',
        'django.contrib.sites',
        'django.contrib.sessions',
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
    # Member avatar tests like to save files to disk,
    # so here's a temporary place for them.
    MEDIA_ROOT=tmp_media.name,
    USE_TZ=True,  # Prevent 'ValueError: SQLite backend does not support
    # timezone-aware datetimes when USE_TZ is False.'
    ROOT_URLCONF='djconnectwise.tests.urls',
    DJCONNECTWISE_CALLBACK_PROTOCOL='http' if DEBUG else 'https',
    DJCONNECTWISE_TEST_DOMAIN='localhost'
)


def _setup():
    """Configure Django stuff for tests."""
    django.setup()
    # Set up the test DB, if necessary.
    # Note that the test DB is not deleted before or after a test,
    # which speeds up subsequent tests because migrations
    # don't need to be run. But if you run into any funny errors,
    # you may want to remove the DB file and start fresh.
    # The DB file is stored in settings.DATABASES['default']['NAME'].
    call_command('migrate')
    # Clear out the test DB
    call_command('flush', '--noinput')


def exit_on_failure(command, message=None):
    if command:
        sys.exit(command)


def flake8_main():
    print('Running: flake8')
    _call = ['flake8'] + ['.']
    command = subprocess.call(_call)

    print("Failed: flake8 failed." if command else "Success. flake8 passed.")
    return command


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
    exit_on_failure(flake8_main())
