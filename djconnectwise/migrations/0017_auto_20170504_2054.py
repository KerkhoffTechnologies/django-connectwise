# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0016_auto_20170404_1504'),
    ]

    operations = [
        migrations.AlterField(
            model_name='member',
            name='created',
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name='member',
            name='modified',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
