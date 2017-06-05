# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0019_ticket_owner'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='customer_updated',
            field=models.BooleanField(default=False),
        ),
    ]
