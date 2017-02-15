# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0008_auto_20170215_1430'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='ticketpriority',
            options={'ordering': ('name',), 'verbose_name_plural': 'ticket priorities'},
        ),
    ]
