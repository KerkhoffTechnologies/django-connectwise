# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0014_company_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='companystatus',
            name='notification_message',
            field=models.CharField(max_length=500, blank=True),
        ),
    ]
