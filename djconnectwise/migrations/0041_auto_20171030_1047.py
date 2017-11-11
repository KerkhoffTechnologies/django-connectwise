# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0040_auto_20170926_2145'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='callbackentry',
            options={'verbose_name_plural': 'Callback entries', 'verbose_name': 'Callback entry'},
        ),
        migrations.AlterModelOptions(
            name='companystatus',
            options={'verbose_name_plural': 'Company statuses'},
        ),
        migrations.AlterModelOptions(
            name='opportunitypriority',
            options={'ordering': ('name',), 'verbose_name_plural': 'opportunity priorities'},
        ),
    ]
