# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0018_auto_20170505_1531'),
    ]

    operations = [
        migrations.AddField(
            model_name='syncjob',
            name='entity_name',
            field=models.CharField(max_length=100, default=''),
            preserve_default=False,
        ),
    ]
