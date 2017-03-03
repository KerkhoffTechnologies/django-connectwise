# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0005_auto_20170225_0101'),
    ]

    operations = [
        migrations.AlterField(
            model_name='callbackentry',
            name='description',
            field=models.CharField(max_length=100, null=True, blank=True),
        ),
    ]
