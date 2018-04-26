# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0053_merge'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='timeentry',
            options={'ordering': ('-time_start', 'id'), 'verbose_name_plural': 'Time Entries'},
        ),
    ]
