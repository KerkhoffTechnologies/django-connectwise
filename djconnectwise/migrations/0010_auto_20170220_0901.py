# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0009_auto_20170215_1438'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ticketpriority',
            name='color',
            field=models.CharField(max_length=50, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='ticketpriority',
            name='sort',
            field=models.PositiveSmallIntegerField(null=True),
        ),
    ]
