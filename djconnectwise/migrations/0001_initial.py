# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import easy_thumbnails.fields
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CallBackEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('callback_type', models.CharField(max_length=25)),
                ('url', models.CharField(max_length=255)),
                ('level', models.CharField(max_length=255)),
                ('object_id', models.IntegerField()),
                ('entry_id', models.IntegerField()),
                ('member_id', models.IntegerField()),
                ('enabled', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='Company',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('company_id', models.PositiveSmallIntegerField()),
                ('company_name', models.CharField(max_length=250, blank=True, null=True)),
                ('company_alias', models.CharField(max_length=250, blank=True, null=True)),
                ('company_identifier', models.CharField(max_length=250, blank=True, null=True)),
                ('phone_number', models.CharField(max_length=250, blank=True, null=True)),
                ('fax_number', models.CharField(max_length=250, blank=True, null=True)),
                ('address_line1', models.CharField(max_length=250, blank=True, null=True)),
                ('address_line2', models.CharField(max_length=250, blank=True, null=True)),
                ('city', models.CharField(max_length=250, blank=True, null=True)),
                ('state_identifier', models.CharField(max_length=250, blank=True, null=True)),
                ('zip', models.CharField(max_length=250, blank=True, null=True)),
                ('country', models.CharField(max_length=250, blank=True, null=True)),
                ('type', models.CharField(max_length=250, blank=True, null=True)),
                ('status', models.CharField(max_length=250, blank=True, null=True)),
                ('territory', models.CharField(max_length=250, blank=True, null=True)),
                ('website', models.CharField(max_length=250, blank=True, null=True)),
                ('market', models.CharField(max_length=250, blank=True, null=True)),
                ('defaultcontactid', models.IntegerField(blank=True, null=True)),
                ('defaultbillingcontactid', models.IntegerField(blank=True, null=True)),
                ('updatedby', models.CharField(max_length=250, blank=True, null=True)),
                ('lastupdated', models.CharField(max_length=250, blank=True, null=True)),
            ],
            options={
                'verbose_name_plural': 'companies',
                'ordering': ('company_identifier',),
            },
        ),
        migrations.CreateModel(
            name='ConnectWiseBoard',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('board_id', models.PositiveSmallIntegerField()),
                ('name', models.CharField(max_length=255)),
                ('inactive', models.BooleanField()),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='ConnectWiseBoardStatus',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('board_id', models.PositiveSmallIntegerField()),
                ('status_id', models.PositiveSmallIntegerField()),
                ('status_name', models.CharField(max_length=250, blank=True, null=True)),
            ],
            options={
                'ordering': ('status_name',),
            },
        ),
        migrations.CreateModel(
            name='Location',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('location_id', models.PositiveSmallIntegerField()),
                ('name', models.CharField(max_length=30)),
                ('where', models.CharField(max_length=100, blank=True, null=True)),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='Member',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('member_id', models.PositiveSmallIntegerField()),
                ('identifier', models.CharField(max_length=15, unique=True)),
                ('first_name', models.CharField(max_length=30)),
                ('last_name', models.CharField(max_length=30)),
                ('office_email', models.EmailField(max_length=250)),
                ('inactive', models.BooleanField(default=False)),
                ('avatar', easy_thumbnails.fields.ThumbnailerImageField(verbose_name='Member Avatar', blank=True, null=True, help_text='Member Avatar', upload_to='')),
            ],
            options={
                'ordering': ('first_name', 'last_name'),
            },
        ),
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(max_length=200)),
                ('project_id', models.PositiveSmallIntegerField()),
                ('project_href', models.CharField(max_length=200)),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='SyncJob',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('start_time', models.DateTimeField(auto_now_add=True)),
                ('end_time', models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Team',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('team_id', models.PositiveSmallIntegerField()),
                ('name', models.CharField(max_length=30)),
                ('board', models.ForeignKey(to='djconnectwise.ConnectWiseBoard')),
                ('members', models.ManyToManyField(to='djconnectwise.Member')),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Ticket',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('closed_flag', models.NullBooleanField()),
                ('type', models.CharField(max_length=250, blank=True, null=True)),
                ('sub_type', models.CharField(max_length=250, blank=True, null=True)),
                ('sub_type_item', models.CharField(max_length=250, blank=True, null=True)),
                ('priority_text', models.CharField(max_length=250, blank=True, null=True)),
                ('source', models.CharField(max_length=250, blank=True, null=True)),
                ('summary', models.CharField(max_length=250, blank=True, null=True)),
                ('entered_date_utc', models.DateTimeField(blank=True, null=True)),
                ('last_updated_utc', models.DateTimeField(blank=True, null=True)),
                ('resources', models.CharField(max_length=250, blank=True, null=True)),
                ('required_date_utc', models.DateTimeField(blank=True, null=True)),
                ('closed_date_utc', models.DateTimeField(blank=True, null=True)),
                ('site_name', models.CharField(max_length=250, blank=True, null=True)),
                ('budget_hours', models.DecimalField(blank=True, null=True, max_digits=6, decimal_places=2)),
                ('actual_hours', models.DecimalField(blank=True, null=True, max_digits=6, decimal_places=2)),
                ('approved', models.NullBooleanField()),
                ('closed_by', models.CharField(max_length=250, blank=True, null=True)),
                ('resolve_mins', models.IntegerField(blank=True, null=True)),
                ('res_plan_mins', models.IntegerField(blank=True, null=True)),
                ('respond_mins', models.IntegerField(blank=True, null=True)),
                ('updated_by', models.CharField(max_length=250, blank=True, null=True)),
                ('record_type', models.CharField(max_length=250, blank=True, null=True, db_index=True, choices=[('Ticket', 'Service Ticket'), ('ProjectTicket', 'Project Ticket'), ('ProjectIssue', 'Project Issue')])),
                ('agreement_id', models.IntegerField(blank=True, null=True)),
                ('severity', models.CharField(max_length=250, blank=True, null=True)),
                ('impact', models.CharField(max_length=250, blank=True, null=True)),
                ('date_resolved_utc', models.DateTimeField(blank=True, null=True)),
                ('date_resplan_utc', models.DateTimeField(blank=True, null=True)),
                ('date_responded_utc', models.DateTimeField(blank=True, null=True)),
                ('is_in_sla', models.NullBooleanField()),
                ('api_text', models.TextField(blank=True, null=True)),
                ('board_name', models.CharField(max_length=250, blank=True, null=True)),
                ('board_id', models.IntegerField(blank=True, null=True, db_index=True)),
                ('board_status_id', models.IntegerField(blank=True, null=True)),
                ('company', models.ForeignKey(blank=True, null=True, related_name='company_tickets', to='djconnectwise.Company')),
                ('location', models.ForeignKey(blank=True, null=True, related_name='location_tickets', to='djconnectwise.Location')),
            ],
            options={
                'verbose_name': 'Ticket',
                'verbose_name_plural': 'Tickets',
                'ordering': ('summary',),
            },
        ),
        migrations.CreateModel(
            name='TicketAssignment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('member', models.ForeignKey(to='djconnectwise.Member')),
                ('service_ticket', models.ForeignKey(to='djconnectwise.Ticket')),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='TicketPriority',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(max_length=50)),
                ('priority_id', models.PositiveSmallIntegerField()),
                ('sort', models.PositiveSmallIntegerField(null=True)),
                ('_color', models.CharField(max_length=50, blank=True, null=True, db_column='color')),
            ],
            options={
                'verbose_name_plural': 'ticket priorities',
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='TicketStatus',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('status_id', models.IntegerField(unique=True, blank=True, null=True)),
                ('ticket_status', models.CharField(max_length=250, blank=True, null=True)),
                ('status_name', models.CharField(max_length=250, blank=True, null=True)),
            ],
            options={
                'verbose_name_plural': 'ticket statuses',
                'ordering': ('ticket_status',),
            },
        ),
        migrations.AddField(
            model_name='ticket',
            name='members',
            field=models.ManyToManyField(related_name='member_tickets', to='djconnectwise.Member', through='djconnectwise.TicketAssignment'),
        ),
        migrations.AddField(
            model_name='ticket',
            name='priority',
            field=models.ForeignKey(blank=True, null=True, to='djconnectwise.TicketPriority'),
        ),
        migrations.AddField(
            model_name='ticket',
            name='project',
            field=models.ForeignKey(blank=True, null=True, related_name='project_tickets', to='djconnectwise.Project'),
        ),
        migrations.AddField(
            model_name='ticket',
            name='status',
            field=models.ForeignKey(blank=True, null=True, related_name='status_tickets', to='djconnectwise.TicketStatus'),
        ),
        migrations.AddField(
            model_name='ticket',
            name='team',
            field=models.ForeignKey(blank=True, null=True, related_name='team_tickets', to='djconnectwise.Team'),
        ),
    ]
