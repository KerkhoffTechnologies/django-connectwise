# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0005_auto_20170127_1549'),
    ]

    operations = [
        migrations.AlterField(
            model_name='serviceticket',
            name='board_id',
            field=models.IntegerField(null=True, blank=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='serviceticket',
            name='record_type',
            field=models.CharField(max_length=250, null=True, blank=True, choices=[('ServiceTicket', 'Service Ticket'), ('ProjectTicket', 'Project Ticket'), ('ProjectIssue', 'Project Issue')], db_index=True),
        ),
    ]
