# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0056_auto_20180504_0744'),
    ]

    operations = [
        migrations.AlterField(
            model_name='opportunity',
            name='business_unit_id',
            field=models.IntegerField(null=True),
        ),
    ]
