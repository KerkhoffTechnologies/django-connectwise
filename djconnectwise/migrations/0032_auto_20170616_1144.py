# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0031_auto_20170607_2234'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ticket',
            name='record_type',
            field=models.CharField(null=True, blank=True, db_index=True, max_length=250, choices=[('ServiceTicket', 'Service Ticket'), ('ProjectTicket', 'Project Ticket'), ('ProjectIssue', 'Project Issue')]),
        ),
    ]
