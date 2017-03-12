# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0008_project_status_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='member',
            name='license_class',
            field=models.CharField(choices=[('F', 'Full license'), ('A', 'API license')], db_index=True, blank=True, max_length=20, null=True),
        ),
    ]
