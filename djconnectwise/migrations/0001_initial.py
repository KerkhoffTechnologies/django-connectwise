# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django_extensions.db.fields
import easy_thumbnails.fields


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CallBackEntry',
            fields=[
                ('id', models.AutoField(auto_created=True,
                                        serialize=False, verbose_name='ID', primary_key=True)),
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
                ('id', models.AutoField(auto_created=True,
                                        serialize=False, verbose_name='ID', primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(
                    auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(
                    auto_now=True, verbose_name='modified')),
                ('company_name', models.CharField(
                    null=True, blank=True, max_length=250)),
                ('company_alias', models.CharField(
                    null=True, blank=True, max_length=250)),
                ('company_identifier', models.CharField(
                    null=True, blank=True, max_length=250)),
                ('phone_number', models.CharField(
                    null=True, blank=True, max_length=250)),
                ('fax_number', models.CharField(
                    null=True, blank=True, max_length=250)),
                ('address_line1', models.CharField(
                    null=True, blank=True, max_length=250)),
                ('address_line2', models.CharField(
                    null=True, blank=True, max_length=250)),
                ('city', models.CharField(null=True, blank=True, max_length=250)),
                ('state_identifier', models.CharField(
                    null=True, blank=True, max_length=250)),
                ('zip', models.CharField(null=True, blank=True, max_length=250)),
                ('country', models.CharField(null=True, blank=True, max_length=250)),
                ('type', models.CharField(null=True, blank=True, max_length=250)),
                ('status', models.CharField(null=True, blank=True, max_length=250)),
                ('territory', models.CharField(
                    null=True, blank=True, max_length=250)),
                ('website', models.CharField(null=True, blank=True, max_length=250)),
                ('market', models.CharField(null=True, blank=True, max_length=250)),
                ('defaultcontactid', models.IntegerField(null=True, blank=True)),
                ('defaultbillingcontactid',
                 models.IntegerField(null=True, blank=True)),
                ('updatedby', models.CharField(
                    null=True, blank=True, max_length=250)),
                ('lastupdated', models.CharField(
                    null=True, blank=True, max_length=250)),
            ],
            options={
                'get_latest_by': 'modified',
                'ordering': ('-modified', '-created'),
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ConnectWiseBoard',
            fields=[
                ('id', models.AutoField(auto_created=True,
                                        serialize=False, verbose_name='ID', primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(
                    auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(
                    auto_now=True, verbose_name='modified')),
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
                ('id', models.AutoField(auto_created=True,
                                        serialize=False, verbose_name='ID', primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(
                    auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(
                    auto_now=True, verbose_name='modified')),
                ('board_id', models.PositiveSmallIntegerField()),
                ('status_id', models.PositiveSmallIntegerField()),
                ('status_name', models.CharField(
                    null=True, blank=True, max_length=250)),
            ],
            options={
                'ordering': ('status_name',),
            },
        ),
        migrations.CreateModel(
            name='Member',
            fields=[
                ('id', models.AutoField(auto_created=True,
                                        serialize=False, verbose_name='ID', primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(
                    auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(
                    auto_now=True, verbose_name='modified')),
                ('first_name', models.CharField(max_length=30)),
                ('last_name', models.CharField(max_length=30)),
                ('identifier', models.CharField(max_length=15)),
                ('office_email', models.EmailField(max_length=250)),
                ('inactive', models.BooleanField(default=False)),
                ('avatar', easy_thumbnails.fields.ThumbnailerImageField(null=True, upload_to='',
                                                                        blank=True, verbose_name='Member Avatar', help_text='Member Avatar')),
            ],
            options={
                'get_latest_by': 'modified',
                'ordering': ('-modified', '-created'),
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.AutoField(auto_created=True,
                                        serialize=False, verbose_name='ID', primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(
                    auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(
                    auto_now=True, verbose_name='modified')),
                ('name', models.CharField(max_length=200)),
                ('project_id', models.PositiveSmallIntegerField()),
                ('project_href', models.CharField(max_length=200)),
            ],
            options={
                'get_latest_by': 'modified',
                'ordering': ('-modified', '-created'),
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ServiceProvider',
            fields=[
                ('id', models.AutoField(auto_created=True,
                                        serialize=False, verbose_name='ID', primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(
                    auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(
                    auto_now=True, verbose_name='modified')),
                ('title', models.CharField(verbose_name='title', max_length=255)),
                ('description', models.TextField(null=True,
                                                 blank=True, verbose_name='description')),
                ('slug', django_extensions.db.fields.AutoSlugField(blank=True,
                                                                   editable=False, verbose_name='slug', populate_from='title')),
                ('logo', easy_thumbnails.fields.ThumbnailerImageField(null=True, upload_to='',
                                                                      blank=True, verbose_name='Service Provider Logo', help_text='Service Provider Logo')),
            ],
            options={
                'get_latest_by': 'modified',
                'ordering': ('-modified', '-created'),
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ServiceTicket',
            fields=[
                ('id', models.AutoField(auto_created=True,
                                        serialize=False, verbose_name='ID', primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(
                    auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(
                    auto_now=True, verbose_name='modified')),
                ('closed_flag', models.NullBooleanField()),
                ('type', models.CharField(null=True, blank=True, max_length=250)),
                ('sub_type', models.CharField(null=True, blank=True, max_length=250)),
                ('sub_type_item', models.CharField(
                    null=True, blank=True, max_length=250)),
                ('priority_text', models.CharField(
                    null=True, blank=True, max_length=250)),
                ('location', models.CharField(null=True, blank=True, max_length=250)),
                ('source', models.CharField(null=True, blank=True, max_length=250)),
                ('summary', models.CharField(null=True, blank=True, max_length=250)),
                ('entered_date_utc', models.DateTimeField(null=True, blank=True)),
                ('last_updated_utc', models.DateTimeField(null=True, blank=True)),
                ('resources', models.CharField(
                    null=True, blank=True, max_length=250)),
                ('required_date_utc', models.DateTimeField(null=True, blank=True)),
                ('closed_date_utc', models.DateTimeField(null=True, blank=True)),
                ('site_name', models.CharField(
                    null=True, blank=True, max_length=250)),
                ('budget_hours', models.DecimalField(null=True,
                                                     blank=True, decimal_places=2, max_digits=6)),
                ('actual_hours', models.DecimalField(null=True,
                                                     blank=True, decimal_places=2, max_digits=6)),
                ('approved', models.NullBooleanField()),
                ('closed_by', models.CharField(
                    null=True, blank=True, max_length=250)),
                ('resolve_mins', models.IntegerField(null=True, blank=True)),
                ('res_plan_mins', models.IntegerField(null=True, blank=True)),
                ('respond_mins', models.IntegerField(null=True, blank=True)),
                ('updated_by', models.CharField(
                    null=True, blank=True, max_length=250)),
                ('record_type', models.CharField(
                    null=True, blank=True, max_length=250)),
                ('team_id', models.IntegerField(null=True, blank=True)),
                ('agreement_id', models.IntegerField(null=True, blank=True)),
                ('severity', models.CharField(null=True, blank=True, max_length=250)),
                ('impact', models.CharField(null=True, blank=True, max_length=250)),
                ('date_resolved_utc', models.DateTimeField(null=True, blank=True)),
                ('date_resplan_utc', models.DateTimeField(null=True, blank=True)),
                ('date_responded_utc', models.DateTimeField(null=True, blank=True)),
                ('is_in_sla', models.NullBooleanField()),
                ('api_text', models.TextField(null=True, blank=True)),
                ('board_name', models.CharField(
                    null=True, blank=True, max_length=250)),
                ('board_id', models.IntegerField(null=True, blank=True)),
                ('board_status_id', models.IntegerField(null=True, blank=True)),
                ('company', models.ForeignKey(blank=True, null=True,
                                              related_name='company_tickets', to='djconnectwise.Company')),
            ],
            options={
                'verbose_name_plural': 'Service Tickets',
                'verbose_name': 'Service Ticket',
            },
        ),
        migrations.CreateModel(
            name='ServiceTicketAssignment',
            fields=[
                ('id', models.AutoField(auto_created=True,
                                        serialize=False, verbose_name='ID', primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(
                    auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(
                    auto_now=True, verbose_name='modified')),
                ('member', models.ForeignKey(to='djconnectwise.Member')),
                ('service_ticket', models.ForeignKey(
                    to='djconnectwise.ServiceTicket')),
            ],
            options={
                'get_latest_by': 'modified',
                'ordering': ('-modified', '-created'),
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='SyncJob',
            fields=[
                ('id', models.AutoField(auto_created=True,
                                        serialize=False, verbose_name='ID', primary_key=True)),
                ('start_time', models.DateTimeField(auto_now_add=True)),
                ('end_time', models.DateTimeField(null=True, blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='TicketPriority',
            fields=[
                ('id', models.AutoField(auto_created=True,
                                        serialize=False, verbose_name='ID', primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(
                    auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(
                    auto_now=True, verbose_name='modified')),
                ('title', models.CharField(verbose_name='title', max_length=255)),
                ('description', models.TextField(null=True,
                                                 blank=True, verbose_name='description')),
            ],
            options={
                'get_latest_by': 'modified',
                'ordering': ('-modified', '-created'),
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='TicketStatus',
            fields=[
                ('id', models.AutoField(auto_created=True,
                                        serialize=False, verbose_name='ID', primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(
                    auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(
                    auto_now=True, verbose_name='modified')),
                ('status_id', models.IntegerField(
                    null=True, blank=True, unique=True)),
                ('ticket_status', models.CharField(
                    null=True, blank=True, max_length=250)),
                ('status_name', models.CharField(
                    null=True, blank=True, max_length=250)),
            ],
            options={
                'get_latest_by': 'modified',
                'ordering': ('-modified', '-created'),
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='serviceticket',
            name='members',
            field=models.ManyToManyField(
                related_name='member_tickets', to='djconnectwise.Member', through='djconnectwise.ServiceTicketAssignment'),
        ),
        migrations.AddField(
            model_name='serviceticket',
            name='priority',
            field=models.ForeignKey(
                blank=True, null=True, to='djconnectwise.TicketPriority'),
        ),
        migrations.AddField(
            model_name='serviceticket',
            name='project',
            field=models.ForeignKey(
                blank=True, null=True, related_name='project_tickets', to='djconnectwise.Project'),
        ),
        migrations.AddField(
            model_name='serviceticket',
            name='status',
            field=models.ForeignKey(
                blank=True, null=True, related_name='status_tickets', to='djconnectwise.TicketStatus'),
        ),
        migrations.AddField(
            model_name='member',
            name='service_provider',
            field=models.ForeignKey(
                related_name='members', to='djconnectwise.ServiceProvider'),
        ),
    ]
