# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0041_auto_20171030_1047'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='ticket',
            name='api_text',
        ),
        migrations.RemoveField(
            model_name='ticket',
            name='type',
        ),
    ]
