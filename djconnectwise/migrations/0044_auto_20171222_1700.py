# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0043_projectstatus'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='project',
            name='status_name',
        ),
        migrations.AddField(
            model_name='project',
            name='status',
            field=models.ForeignKey(to='djconnectwise.ProjectStatus', blank=True, null=True),
        ),
    ]
