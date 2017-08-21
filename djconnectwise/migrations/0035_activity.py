# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0034_auto_20170727_1243'),
    ]

    operations = [
        migrations.CreateModel(
            name='Activity',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, verbose_name='ID', primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(max_length=250)),
                ('notes', models.CharField(max_length=1000, blank=True, null=True)),
                ('date_start', models.DateTimeField(blank=True, null=True)),
                ('date_end', models.DateTimeField(blank=True, null=True)),
                ('assign_to', models.ForeignKey(to='djconnectwise.Member')),
                ('opportunity', models.ForeignKey(to='djconnectwise.Opportunity', blank=True, null=True)),
                ('ticket', models.ForeignKey(to='djconnectwise.Ticket', blank=True, null=True)),
            ],
            options={
                'verbose_name_plural': 'activities',
                'ordering': ('opportunity', 'ticket'),
            },
        ),
    ]
