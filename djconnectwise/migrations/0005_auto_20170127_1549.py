# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0004_auto_20170126_1231'),
    ]

    operations = [
        migrations.AlterField(
            model_name='serviceticket',
            name='record_type',
            field=models.CharField(blank=True, choices=[('ServiceTicket', 'Service Ticket'), ('ProjectTicket', 'Project Ticket'), ('ProjectIssue', 'Project Issue')], null=True, max_length=250),
        ),
    ]
