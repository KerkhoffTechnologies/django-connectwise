# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0011_member_member_id'),
    ]

    operations = [
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
        migrations.AlterField(
            model_name='serviceticket',
            name='location',
            field=models.ForeignKey(blank=True, null=True, related_name='location_tickets', to='djconnectwise.Location'),
        ),
    ]
