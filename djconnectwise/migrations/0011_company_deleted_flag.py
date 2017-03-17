# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0010_remove_project_project_href'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='deleted_flag',
            field=models.BooleanField(default=False),
        ),
    ]
