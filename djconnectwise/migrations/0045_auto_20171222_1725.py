# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0044_auto_20171222_1700'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='actual_hours',
            field=models.DecimalField(max_digits=6, blank=True, null=True, decimal_places=2),
        ),
        migrations.AddField(
            model_name='project',
            name='budget_hours',
            field=models.DecimalField(max_digits=6, blank=True, null=True, decimal_places=2),
        ),
        migrations.AddField(
            model_name='project',
            name='scheduled_hours',
            field=models.DecimalField(max_digits=6, blank=True, null=True, decimal_places=2),
        ),
    ]
