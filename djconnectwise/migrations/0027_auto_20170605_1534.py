# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0026_merge'),
    ]

    operations = [
        migrations.AlterField(
            model_name='opportunity',
            name='source',
            field=models.CharField(max_length=100, blank=True, null=True),
        ),
    ]
