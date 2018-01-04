# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0045_auto_20171222_1725'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scheduleentry',
            name='name',
            field=models.CharField(null=True, max_length=250, blank=True),
        ),
    ]
