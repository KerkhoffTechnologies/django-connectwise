# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0013_auto_20170403_1203'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='status',
            field=models.ForeignKey(blank=True, null=True, to='djconnectwise.CompanyStatus'),
        ),
    ]
