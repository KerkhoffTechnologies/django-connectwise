# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0004_auto_20170224_1853'),
    ]

    operations = [
        migrations.RenameField(
            model_name='callbackentry',
            old_name='enabled',
            new_name='inactive_flag',
        ),
        migrations.RemoveField(
            model_name='callbackentry',
            name='entry_id',
        ),
        migrations.AddField(
            model_name='callbackentry',
            name='description',
            field=models.CharField(max_length=100, default=''),
            preserve_default=False,
        ),
    ]
