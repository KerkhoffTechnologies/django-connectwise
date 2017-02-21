# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='connectwiseboardstatus',
            name='board_id',
        ),
        migrations.AddField(
            model_name='connectwiseboardstatus',
            name='board',
            field=models.ForeignKey(default=0, to='djconnectwise.ConnectWiseBoard'),
            preserve_default=False,
        ),
    ]
