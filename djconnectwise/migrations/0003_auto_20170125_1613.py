# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0002_auto_20170125_1127'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='company',
            options={'verbose_name_plural': 'companies'},
        ),
        migrations.AlterModelOptions(
            name='ticketstatus',
            options={'verbose_name_plural': 'ticket statuses'},
        ),
        migrations.AlterField(
            model_name='member',
            name='identifier',
            field=models.CharField(max_length=15, unique=True),
        ),
    ]
