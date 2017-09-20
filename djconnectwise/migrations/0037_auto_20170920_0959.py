# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0036_auto_20170823_1417'),
    ]

    operations = [
        migrations.RenameField(
            model_name='opportunity',
            old_name='type',
            new_name='opportunity_type',
        ),
        migrations.AlterField(
            model_name='opportunity',
            name='company',
            field=models.ForeignKey(to='djconnectwise.Company', related_name='company_opportunities', null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='opportunity',
            name='expected_close_date',
            field=models.DateTimeField(),
        ),
    ]
