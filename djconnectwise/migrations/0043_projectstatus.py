# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0042_auto_20171115_1131'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectStatus',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('name', models.CharField(max_length=30)),
                ('default_flag', models.BooleanField(default=False)),
                ('inactive_flag', models.BooleanField(default=False)),
                ('closed_flag', models.BooleanField(default=False)),
            ],
            options={
                'verbose_name_plural': 'Project statuses',
                'ordering': ('name',),
            },
        ),
    ]
