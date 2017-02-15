# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0007_auto_20170215_1918'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='company',
            options={'verbose_name_plural': 'companies', 'ordering': ('company_identifier',)},
        ),
        migrations.AlterModelOptions(
            name='member',
            options={'ordering': ('first_name', 'last_name')},
        ),
        migrations.AlterModelOptions(
            name='project',
            options={'ordering': ('name',)},
        ),
        migrations.AlterModelOptions(
            name='serviceticket',
            options={'verbose_name_plural': 'Service Tickets', 'verbose_name': 'Service Ticket', 'ordering': ('summary',)},
        ),
        migrations.AlterModelOptions(
            name='ticketpriority',
            options={'ordering': ('name',)},
        ),
        migrations.AlterModelOptions(
            name='ticketstatus',
            options={'verbose_name_plural': 'ticket statuses', 'ordering': ('ticket_status',)},
        ),
    ]
