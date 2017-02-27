# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0003_auto_20170223_2233'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='project_href',
            field=models.CharField(max_length=200, blank=True, null=True),
        ),
    ]
