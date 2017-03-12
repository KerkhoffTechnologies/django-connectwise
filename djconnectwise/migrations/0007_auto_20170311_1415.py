# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0006_auto_20170303_1242'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='boardstatus',
            options={'ordering': ('board__name', 'sort_order', 'name'), 'verbose_name_plural': 'Board statuses'},
        ),
        migrations.AlterModelOptions(
            name='connectwiseboard',
            options={'verbose_name': 'ConnectWise board', 'ordering': ('name',)},
        ),
    ]
