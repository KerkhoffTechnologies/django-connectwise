# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0046_auto_20180104_1504'),
    ]

    operations = [
        migrations.AddField(
            model_name='syncjob',
            name='sync_type',
            field=models.TextField(default='full'),
        ),
    ]
