# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0009_member_license_class'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='project',
            name='project_href',
        ),
    ]
