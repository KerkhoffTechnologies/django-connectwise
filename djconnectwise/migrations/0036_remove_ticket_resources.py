# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0035_auto_20170719_1712'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='ticket',
            name='resources',
        ),
    ]
