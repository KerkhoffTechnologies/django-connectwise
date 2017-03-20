# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0011_company_deleted_flag'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='has_child_ticket',
            field=models.NullBooleanField(),
        ),
        migrations.AddField(
            model_name='ticket',
            name='parent_ticket_id',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
