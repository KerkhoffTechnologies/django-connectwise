# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0027_auto_20170605_1534'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='company',
            name='company_alias',
        ),
    ]
