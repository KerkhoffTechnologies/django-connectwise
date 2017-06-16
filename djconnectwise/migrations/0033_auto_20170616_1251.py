# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0032_auto_20170616_1144'),
    ]

    operations = [
        migrations.AlterField(
            model_name='syncjob',
            name='start_time',
            field=models.DateTimeField(),
        ),
    ]
