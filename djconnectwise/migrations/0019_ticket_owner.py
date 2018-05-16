# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0018_auto_20170505_1531'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='owner',
            field=models.ForeignKey(blank=True, null=True, to='djconnectwise.Member', on_delete=models.SET_NULL),
        ),
    ]
