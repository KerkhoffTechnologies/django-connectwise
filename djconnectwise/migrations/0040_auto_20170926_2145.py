# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0039_auto_20170925_1418'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='opportunity',
            options={'verbose_name_plural': 'Opportunities', 'ordering': ('name',)},
        ),
        migrations.AlterModelOptions(
            name='opportunitystatus',
            options={'verbose_name_plural': 'Opportunity statuses', 'ordering': ('name',)},
        ),
        migrations.AlterModelOptions(
            name='scheduleentry',
            options={'verbose_name_plural': 'Schedule entries', 'ordering': ('name',)},
        ),
        migrations.AlterModelOptions(
            name='schedulestatus',
            options={'verbose_name_plural': 'Schedule statuses'},
        ),
    ]
