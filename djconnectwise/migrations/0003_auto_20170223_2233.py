# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0002_auto_20170223_2143'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='boardstatus',
            options={'ordering': ('board__name', 'sort_order', 'name')},
        ),
    ]
