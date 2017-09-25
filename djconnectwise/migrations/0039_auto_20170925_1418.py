# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0038_auto_20170920_1138'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='opportunity',
            options={'ordering': ('name',)},
        ),
        migrations.AlterModelOptions(
            name='opportunitypriority',
            options={'ordering': ('name',)},
        ),
        migrations.AlterModelOptions(
            name='opportunitystage',
            options={'ordering': ('name',)},
        ),
        migrations.AlterModelOptions(
            name='opportunitystatus',
            options={'ordering': ('name',)},
        ),
        migrations.AlterModelOptions(
            name='opportunitytype',
            options={'ordering': ('description',)},
        ),
    ]
