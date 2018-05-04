# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0055_auto_20180501_1022'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='opportunitynote',
            options={'verbose_name_plural': 'Opportunity Notes', 'ordering': ('-date_created', 'id')},
        ),
        migrations.AddField(
            model_name='opportunitynote',
            name='date_created',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
