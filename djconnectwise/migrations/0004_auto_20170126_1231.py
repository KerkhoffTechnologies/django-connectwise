# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0003_auto_20170125_1613'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='ticketpriority',
            name='description',
        ),
        migrations.RenameField(
            model_name='ticketpriority',
            old_name='title',
            new_name='name',
        ),
        migrations.AlterField(
            model_name='ticketpriority',
            name='name',
            field=models.CharField(max_length=50),
            preserve_default=False,
        ),
    ]
