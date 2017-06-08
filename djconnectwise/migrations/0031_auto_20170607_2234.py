# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0030_merge'),
    ]

    operations = [
        migrations.AlterField(
            model_name='syncjob',
            name='added',
            field=models.PositiveIntegerField(null=True),
        ),
        migrations.AlterField(
            model_name='syncjob',
            name='deleted',
            field=models.PositiveIntegerField(null=True),
        ),
        migrations.AlterField(
            model_name='syncjob',
            name='message',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='syncjob',
            name='updated',
            field=models.PositiveIntegerField(null=True),
        ),
    ]
