# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0011_auto_20170220_1013'),
    ]

    operations = [
        migrations.RenameField(
            model_name='ticketpriority',
            old_name='color',
            new_name='_color',
        ),
    ]
