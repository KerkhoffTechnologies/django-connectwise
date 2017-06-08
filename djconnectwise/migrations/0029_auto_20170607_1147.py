# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0028_merge'),
    ]

    operations = [
        migrations.AddField(
            model_name='syncjob',
            name='added',
            field=models.PositiveSmallIntegerField(null=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='syncjob',
            name='deleted',
            field=models.PositiveSmallIntegerField(null=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='syncjob',
            name='message',
            field=models.CharField(max_length=100, default=None, blank=True, null=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='syncjob',
            name='success',
            field=models.NullBooleanField(),
        ),
        migrations.AddField(
            model_name='syncjob',
            name='updated',
            field=models.PositiveSmallIntegerField(null=True),
            preserve_default=False,
        ),
    ]
