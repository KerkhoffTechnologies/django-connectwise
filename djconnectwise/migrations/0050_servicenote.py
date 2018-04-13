# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0049_auto_20180205_1122'),
    ]

    operations = [
        migrations.CreateModel(
            name='ServiceNote',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, primary_key=True, auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('text', models.TextField(null=True, blank=True, max_length=2000)),
                ('detail_description_flag', models.BooleanField()),
                ('internal_analysis_flag', models.BooleanField()),
                ('resolution_flag', models.BooleanField()),
                ('date_created', models.DateTimeField(null=True, blank=True)),
                ('created_by', models.TextField(null=True, blank=True, max_length=250)),
                ('internal_flag', models.BooleanField()),
                ('external_flag', models.BooleanField()),
                ('member', models.ForeignKey(blank=True, null=True, to='djconnectwise.Member')),
                ('ticket', models.ForeignKey(to='djconnectwise.Ticket')),
            ],
            options={
                'ordering': ('date_created', 'id'),
                'verbose_name_plural': 'Notes',
            },
        ),
    ]
