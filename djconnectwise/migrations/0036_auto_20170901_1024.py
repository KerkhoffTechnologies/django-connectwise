# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0035_activity'),
    ]

    operations = [
        migrations.AlterField(
            model_name='opportunity',
            name='company',
            field=models.ForeignKey(blank=True, related_name='company_opportunities', null=True, to='djconnectwise.Company'),
        ),
    ]
