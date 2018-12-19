# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django_extensions.db.fields
#import easy_thumbnails.fields


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='BoardStatus',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(null=True, blank=True, max_length=250)),
                ('sort_order', models.PositiveSmallIntegerField()),
                ('display_on_board', models.BooleanField()),
                ('inactive', models.BooleanField()),
                ('closed_status', models.BooleanField()),
            ],
            options={
                'ordering': ('sort_order',),
            },
        ),
        migrations.CreateModel(
            name='CallBackEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('callback_type', models.CharField(max_length=25)),
                ('url', models.CharField(max_length=255)),
                ('level', models.CharField(max_length=255)),
                ('object_id', models.IntegerField()),
                ('entry_id', models.IntegerField()),
                ('enabled', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='Company',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(null=True, blank=True, max_length=250)),
                ('company_alias', models.CharField(null=True, blank=True, max_length=250)),
                ('identifier', models.CharField(null=True, blank=True, max_length=250)),
                ('phone_number', models.CharField(null=True, blank=True, max_length=250)),
                ('fax_number', models.CharField(null=True, blank=True, max_length=250)),
                ('address_line1', models.CharField(null=True, blank=True, max_length=250)),
                ('address_line2', models.CharField(null=True, blank=True, max_length=250)),
                ('city', models.CharField(null=True, blank=True, max_length=250)),
                ('state_identifier', models.CharField(null=True, blank=True, max_length=250)),
                ('zip', models.CharField(null=True, blank=True, max_length=250)),
                ('country', models.CharField(null=True, blank=True, max_length=250)),
                ('type', models.CharField(null=True, blank=True, max_length=250)),
                ('status', models.CharField(null=True, blank=True, max_length=250)),
                ('territory', models.CharField(null=True, blank=True, max_length=250)),
                ('website', models.CharField(null=True, blank=True, max_length=250)),
                ('market', models.CharField(null=True, blank=True, max_length=250)),
                ('defaultcontactid', models.IntegerField(null=True, blank=True)),
                ('defaultbillingcontactid', models.IntegerField(null=True, blank=True)),
                ('updatedby', models.CharField(null=True, blank=True, max_length=250)),
                ('lastupdated', models.CharField(null=True, blank=True, max_length=250)),
            ],
            options={
                'ordering': ('identifier',),
                'verbose_name_plural': 'companies',
            },
        ),
        migrations.CreateModel(
            name='ConnectWiseBoard',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(max_length=255)),
                ('inactive', models.BooleanField()),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='Location',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(max_length=30)),
                ('where', models.CharField(null=True, blank=True, max_length=100)),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='Member',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('identifier', models.CharField(unique=True, max_length=15)),
                ('first_name', models.CharField(max_length=30)),
                ('last_name', models.CharField(max_length=30)),
                ('office_email', models.EmailField(max_length=250)),
                ('inactive', models.BooleanField(default=False)),
                #('avatar', easy_thumbnails.fields.ThumbnailerImageField(verbose_name='Member Avatar', null=True, help_text='Member Avatar', blank=True, upload_to='')),
                ('avatar', models.CharField(verbose_name='Member Avatar', null=True, help_text='Member Avatar', blank=True)),
            ],
            options={
                'ordering': ('first_name', 'last_name'),
            },
        ),
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(max_length=200)),
                ('project_href', models.CharField(max_length=200)),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='SyncJob',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('start_time', models.DateTimeField(auto_now_add=True)),
                ('end_time', models.DateTimeField(null=True, blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='Team',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(max_length=30)),
                ('board', models.ForeignKey(to='djconnectwise.ConnectWiseBoard', on_delete=models.CASCADE)),
                ('members', models.ManyToManyField(to='djconnectwise.Member')),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'abstract': False,
                'get_latest_by': 'modified',
            },
        ),
        migrations.CreateModel(
            name='Ticket',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('closed_flag', models.NullBooleanField()),
                ('type', models.CharField(null=True, blank=True, max_length=250)),
                ('sub_type', models.CharField(null=True, blank=True, max_length=250)),
                ('sub_type_item', models.CharField(null=True, blank=True, max_length=250)),
                ('source', models.CharField(null=True, blank=True, max_length=250)),
                ('summary', models.CharField(null=True, blank=True, max_length=250)),
                ('entered_date_utc', models.DateTimeField(null=True, blank=True)),
                ('last_updated_utc', models.DateTimeField(null=True, blank=True)),
                ('resources', models.CharField(null=True, blank=True, max_length=250)),
                ('required_date_utc', models.DateTimeField(null=True, blank=True)),
                ('closed_date_utc', models.DateTimeField(null=True, blank=True)),
                ('site_name', models.CharField(null=True, blank=True, max_length=250)),
                ('budget_hours', models.DecimalField(null=True, blank=True, max_digits=6, decimal_places=2)),
                ('actual_hours', models.DecimalField(null=True, blank=True, max_digits=6, decimal_places=2)),
                ('approved', models.NullBooleanField()),
                ('closed_by', models.CharField(null=True, blank=True, max_length=250)),
                ('resolve_mins', models.IntegerField(null=True, blank=True)),
                ('res_plan_mins', models.IntegerField(null=True, blank=True)),
                ('respond_mins', models.IntegerField(null=True, blank=True)),
                ('updated_by', models.CharField(null=True, blank=True, max_length=250)),
                ('record_type', models.CharField(null=True, choices=[('Ticket', 'Service Ticket'), ('ProjectTicket', 'Project Ticket'), ('ProjectIssue', 'Project Issue')], blank=True, db_index=True, max_length=250)),
                ('agreement_id', models.IntegerField(null=True, blank=True)),
                ('severity', models.CharField(null=True, blank=True, max_length=250)),
                ('impact', models.CharField(null=True, blank=True, max_length=250)),
                ('date_resolved_utc', models.DateTimeField(null=True, blank=True)),
                ('date_resplan_utc', models.DateTimeField(null=True, blank=True)),
                ('date_responded_utc', models.DateTimeField(null=True, blank=True)),
                ('is_in_sla', models.NullBooleanField()),
                ('api_text', models.TextField(null=True, blank=True)),
                ('board', models.ForeignKey(blank=True, to='djconnectwise.ConnectWiseBoard', null=True, on_delete=models.CASCADE)),
                ('company', models.ForeignKey(blank=True, to='djconnectwise.Company', null=True, related_name='company_tickets', on_delete=models.SET_NULL)),
                ('location', models.ForeignKey(blank=True, to='djconnectwise.Location', null=True, related_name='location_tickets', on_delete=models.SET_NULL)),
            ],
            options={
                'verbose_name': 'Ticket',
                'ordering': ('summary',),
                'verbose_name_plural': 'Tickets',
            },
        ),
        migrations.CreateModel(
            name='TicketAssignment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('member', models.ForeignKey(to='djconnectwise.Member', on_delete=models.CASCADE)),
                ('ticket', models.ForeignKey(to='djconnectwise.Ticket', on_delete=models.CASCADE)),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'abstract': False,
                'get_latest_by': 'modified',
            },
        ),
        migrations.CreateModel(
            name='TicketPriority',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(max_length=50)),
                ('sort', models.PositiveSmallIntegerField(null=True)),
                ('_color', models.CharField(db_column='color', null=True, blank=True, max_length=50)),
            ],
            options={
                'ordering': ('name',),
                'verbose_name_plural': 'ticket priorities',
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
            field=models.ForeignKey(blank=True, to='djconnectwise.TicketPriority', null=True, on_delete=models.SET_NULL),
        ),
        migrations.AddField(
            model_name='ticket',
            name='project',
            field=models.ForeignKey(blank=True, to='djconnectwise.Project', null=True, related_name='project_tickets', on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='ticket',
            name='status',
            field=models.ForeignKey(blank=True, to='djconnectwise.BoardStatus', null=True, related_name='status_tickets', on_delete=models.SET_NULL),
        ),
        migrations.AddField(
            model_name='ticket',
            name='team',
            field=models.ForeignKey(blank=True, to='djconnectwise.Team', null=True, related_name='team_tickets', on_delete=models.SET_NULL),
        ),
        migrations.AddField(
            model_name='callbackentry',
            name='member',
            field=models.ForeignKey(to='djconnectwise.Member', on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='boardstatus',
            name='board',
            field=models.ForeignKey(to='djconnectwise.ConnectWiseBoard', on_delete=models.CASCADE),
        ),
    ]
