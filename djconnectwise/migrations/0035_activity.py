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
                ('id', models.AutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(max_length=250, null=True, blank=True)),
                ('notes', models.CharField(max_length=1000, null=True, blank=True)),
                ('date_start', models.DateTimeField(null=True, blank=True)),
                ('date_end', models.DateTimeField(null=True, blank=True)),
                ('assign_to', models.ForeignKey(to='djconnectwise.Member')),
                ('opportunity', models.ForeignKey(null=True, blank=True, to='djconnectwise.Opportunity')),
                ('ticket', models.ForeignKey(null=True, blank=True, to='djconnectwise.Ticket')),
            ],
            options={
                'ordering': ('opportunity', 'ticket'),
                'verbose_name_plural': 'activities',
            },
        ),
    ]
