# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0037_merge'),
    ]

    operations = [
        migrations.AlterField(
            model_name='opportunity',
            name='expected_close_date',
            field=models.DateTimeField(),
        ),
    ]
