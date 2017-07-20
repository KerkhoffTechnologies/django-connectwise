# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0034_auto_20170719_1324'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='ticketassignment',
            name='member',
        ),
        migrations.RemoveField(
            model_name='ticketassignment',
            name='ticket',
        ),
        migrations.RemoveField(
            model_name='ticket',
            name='members',
        ),
        migrations.DeleteModel(
            name='TicketAssignment',
        ),
    ]
