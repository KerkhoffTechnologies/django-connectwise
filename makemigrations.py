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
)


def makemigrations():
    django.setup()
    call_command('makemigrations', 'djconnectwise')


if __name__ == '__main__':
    makemigrations()
