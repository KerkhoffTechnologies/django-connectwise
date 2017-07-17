# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0033_auto_20170616_1251'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScheduleEntry',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', serialize=False, auto_created=True)),
                ('name', models.CharField(max_length=250)),
                ('date_start', models.DateTimeField(blank=True, null=True)),
                ('date_end', models.DateTimeField(blank=True, null=True)),
                ('done_flag', models.BooleanField(default=False)),
                ('member', models.ForeignKey(to='djconnectwise.Member')),
                ('object', models.ForeignKey(to='djconnectwise.Ticket')),
            ],
        ),
        migrations.CreateModel(
            name='ScheduleStatus',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', serialize=False, auto_created=True)),
                ('name', models.CharField(max_length=30)),
            ],
        ),
        migrations.CreateModel(
            name='ScheduleType',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', serialize=False, auto_created=True)),
                ('name', models.CharField(max_length=50)),
                ('identifier', models.CharField(max_length=1)),
            ],
        ),
        migrations.AddField(
            model_name='scheduleentry',
            name='schedule_type',
            field=models.ForeignKey(to='djconnectwise.ScheduleType', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='scheduleentry',
            name='status',
            field=models.ForeignKey(to='djconnectwise.ScheduleStatus', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='scheduleentry',
            name='where',
            field=models.ForeignKey(to='djconnectwise.Location', blank=True, null=True),
        ),
    ]
