# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0012_auto_20170320_1057'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompanyStatus',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('name', models.CharField(max_length=50)),
                ('default_flag', models.BooleanField()),
                ('inactive_flag', models.BooleanField()),
                ('notify_flag', models.BooleanField()),
                ('dissalow_saving_flag', models.BooleanField()),
                ('notification_message', models.CharField(max_length=500)),
                ('custom_note_flag', models.BooleanField()),
                ('cancel_open_tracks_flag', models.BooleanField()),
                ('track_id', models.PositiveSmallIntegerField(blank=True, null=True)),
            ],
        ),
    ]
