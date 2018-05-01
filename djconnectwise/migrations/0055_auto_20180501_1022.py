# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0054_auto_20180501_1009'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='servicenote',
            options={'verbose_name_plural': 'Notes', 'ordering': ('-date_created', 'id')},
        ),
    ]
