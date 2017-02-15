# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0006_auto_20170130_1641'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticketpriority',
            name='color',
            field=models.CharField(max_length=50, default='blue'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='ticketpriority',
            name='priority_id',
            field=models.PositiveSmallIntegerField(default=1),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='ticketpriority',
            name='sort',
            field=models.PositiveSmallIntegerField(default=0),
            preserve_default=False,
        ),
    ]
