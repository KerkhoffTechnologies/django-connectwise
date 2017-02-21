# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0010_auto_20170220_0901'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ticketpriority',
            name='color',
            field=models.CharField(db_column='color', max_length=50, blank=True, null=True),
        ),
    ]
