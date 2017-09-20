# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0037_auto_20170920_0959'),
    ]

    operations = [
        migrations.AlterField(
            model_name='opportunity',
            name='expected_close_date',
            field=models.DateField(),
        ),
    ]
