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
                ('id', models.AutoField(serialize=False, auto_created=True, primary_key=True, verbose_name='ID')),
                ('name', models.CharField(max_length=250)),
                ('expected_date_start', models.DateTimeField(blank=True, null=True)),
                ('expected_date_end', models.DateTimeField(blank=True, null=True)),
                ('done_flag', models.BooleanField(default=False)),
                ('member', models.ForeignKey(to='djconnectwise.Member')),
                ('object', models.ForeignKey(to='djconnectwise.Ticket')),
            ],
        ),
        migrations.CreateModel(
            name='ScheduleStatus',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, primary_key=True, verbose_name='ID')),
                ('name', models.CharField(max_length=30)),
            ],
        ),
        migrations.CreateModel(
            name='ScheduleType',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, primary_key=True, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('identifier', models.CharField(max_length=1)),
            ],
        ),
        migrations.AddField(
            model_name='scheduleentry',
            name='schedule_type',
            field=models.ForeignKey(blank=True, null=True, to='djconnectwise.ScheduleType'),
        ),
        migrations.AddField(
            model_name='scheduleentry',
            name='status',
            field=models.ForeignKey(blank=True, null=True, to='djconnectwise.ScheduleStatus'),
        ),
        migrations.AddField(
            model_name='scheduleentry',
            name='where',
            field=models.ForeignKey(blank=True, null=True, to='djconnectwise.Location'),
        ),
    ]
