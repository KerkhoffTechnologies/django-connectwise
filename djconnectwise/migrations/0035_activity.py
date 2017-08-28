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
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('name', models.CharField(max_length=250)),
                ('notes', models.TextField(blank=True, null=True, max_length=2000)),
                ('date_start', models.DateTimeField(blank=True, null=True)),
                ('date_end', models.DateTimeField(blank=True, null=True)),
                ('assign_to', models.ForeignKey(to='djconnectwise.Member')),
                ('opportunity', models.ForeignKey(null=True, blank=True, to='djconnectwise.Opportunity')),
                ('ticket', models.ForeignKey(null=True, blank=True, to='djconnectwise.Ticket')),
            ],
            options={
                'verbose_name_plural': 'activities',
            },
        ),
    ]
