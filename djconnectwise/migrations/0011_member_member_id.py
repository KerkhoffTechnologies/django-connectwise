# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0010_auto_20170217_1953'),
    ]

    operations = [
        migrations.AddField(
            model_name='member',
            name='member_id',
            field=models.PositiveSmallIntegerField(default=1),
            preserve_default=False,
        ),
    ]
