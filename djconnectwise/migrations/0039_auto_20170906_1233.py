# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0038_auto_20170905_1246'),
    ]

    operations = [
        migrations.RenameField(
            model_name='opportunity',
            old_name='type',
            new_name='opportunity_type',
        ),
    ]
