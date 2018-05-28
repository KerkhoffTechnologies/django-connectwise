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
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID', auto_created=True)),
                ('name', models.CharField(max_length=250)),
                ('expected_date_start', models.DateTimeField(null=True, blank=True)),
                ('expected_date_end', models.DateTimeField(null=True, blank=True)),
                ('done_flag', models.BooleanField(default=False)),
                ('activity_object', models.ForeignKey(blank=True, null=True, to='djconnectwise.Activity', on_delete=models.CASCADE)),
                ('member', models.ForeignKey(to='djconnectwise.Member', on_delete=models.CASCADE)),
            ],
            options={
                'ordering': ('name',),
                'verbose_name_plural': 'Schedule Entries',
            },
        ),
        migrations.CreateModel(
            name='ScheduleStatus',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID', auto_created=True)),
                ('name', models.CharField(max_length=30)),
            ],
        ),
        migrations.CreateModel(
            name='ScheduleType',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID', auto_created=True)),
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
        migrations.AlterField(
            model_name='ticket',
            name='members',
            field=models.ManyToManyField(related_name='member_tickets', to='djconnectwise.Member', through='djconnectwise.ScheduleEntry'),
        ),
        migrations.DeleteModel(
            name='TicketAssignment',
        ),
        migrations.AddField(
            model_name='scheduleentry',
            name='schedule_type',
            field=models.ForeignKey(blank=True, null=True, to='djconnectwise.ScheduleType', on_delete=models.SET_NULL),
        ),
        migrations.AddField(
            model_name='scheduleentry',
            name='status',
            field=models.ForeignKey(blank=True, null=True, to='djconnectwise.ScheduleStatus', on_delete=models.SET_NULL),
        ),
        migrations.AddField(
            model_name='scheduleentry',
            name='ticket_object',
            field=models.ForeignKey(blank=True, null=True, to='djconnectwise.Ticket', on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='scheduleentry',
            name='where',
            field=models.ForeignKey(blank=True, null=True, to='djconnectwise.Location', on_delete=models.SET_NULL),
        ),
    ]
