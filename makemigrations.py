#!/usr/bin/env python
import django

from django.conf import settings
from django.core.management import call_command

settings.configure(
    DEBUG=True,
    INSTALLED_APPS=(
        'djconnectwise',
        'easy_thumbnails',
    ),
    DJCONNECTWISE_API_BATCH_LIMIT=25,
)


def makemigrations():
    django.setup()
    # If a migration ever says to run makemigrations --merge, run this:
    # call_command('makemigrations', 'djconnectwise', '--merge')
    # (And consider adding --merge to this script.)
    call_command('makemigrations', 'djconnectwise')


if __name__ == '__main__':
    makemigrations()
