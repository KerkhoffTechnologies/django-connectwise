# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0033_auto_20170616_1251'),
    ]

    operations = [
        migrations.AlterField(
            model_name='opportunity',
            name='notes',
            field=models.TextField(null=True, blank=True),
        ),
    ]
