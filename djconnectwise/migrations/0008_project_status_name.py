# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0007_auto_20170311_1415'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='status_name',
            field=models.CharField(max_length=200, blank=True, null=True),
        ),
    ]
