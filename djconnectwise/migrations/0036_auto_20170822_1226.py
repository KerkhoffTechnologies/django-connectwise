# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0035_activity'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScheduleEntry',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
                ('name', models.CharField(max_length=250)),
                ('expected_date_start', models.DateTimeField(null=True, blank=True)),
                ('expected_date_end', models.DateTimeField(null=True, blank=True)),
                ('done_flag', models.BooleanField(default=False)),
                ('member', models.ForeignKey(to='djconnectwise.Member')),
            ],
            options={
                'ordering': ('name',),
                'verbose_name_plural': 'Schedule Entries',
            },
        ),
        migrations.CreateModel(
            name='ScheduleStatus',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
                ('name', models.CharField(max_length=30)),
            ],
        ),
        migrations.CreateModel(
            name='ScheduleType',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
                ('name', models.CharField(max_length=50)),
                ('identifier', models.CharField(max_length=1)),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.RemoveField(
            model_name='ticketassignment',
            name='member',
        ),
        migrations.RemoveField(
            model_name='ticketassignment',
            name='ticket',
        ),
        migrations.RemoveField(
            model_name='ticket',
            name='resources',
        ),
        migrations.AlterField(
            model_name='ticket',
            name='members',
            field=models.ManyToManyField(through='djconnectwise.ScheduleEntry', to='djconnectwise.Member', related_name='member_tickets'),
        ),
        migrations.DeleteModel(
            name='TicketAssignment',
        ),
        migrations.AddField(
            model_name='scheduleentry',
            name='object',
            field=models.ForeignKey(to='djconnectwise.Ticket'),
        ),
        migrations.AddField(
            model_name='scheduleentry',
            name='schedule_type',
            field=models.ForeignKey(blank=True, to='djconnectwise.ScheduleType', null=True),
        ),
        migrations.AddField(
            model_name='scheduleentry',
            name='status',
            field=models.ForeignKey(blank=True, to='djconnectwise.ScheduleStatus', null=True),
        ),
        migrations.AddField(
            model_name='scheduleentry',
            name='where',
            field=models.ForeignKey(blank=True, to='djconnectwise.Location', null=True),
        ),
    ]
