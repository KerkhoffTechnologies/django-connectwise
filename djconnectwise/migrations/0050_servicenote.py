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
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('text', models.TextField(blank=True, max_length=2000, null=True)),
                ('detail_description_flag', models.BooleanField()),
                ('internal_analysis_flag', models.BooleanField()),
                ('resolution_flag', models.BooleanField()),
                ('date_created', models.DateTimeField(blank=True, null=True)),
                ('created_by', models.TextField(blank=True, max_length=250, null=True)),
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
