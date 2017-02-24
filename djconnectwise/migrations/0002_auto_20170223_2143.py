# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='connectwiseboard',
            name='inactive',
            field=models.BooleanField(default=False),
        ),
    ]
