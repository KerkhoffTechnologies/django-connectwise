# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0050_servicenote'),
    ]

    operations = [
        migrations.CreateModel(
            name='OpportunityNote',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, verbose_name='ID', primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('text', models.TextField(blank=True, null=True, max_length=2000)),
                ('opportunity', models.ForeignKey(to='djconnectwise.Opportunity', on_delete=models.CASCADE)),
            ],
            options={
                'verbose_name_plural': 'Opportunity Notes',
                'ordering': ('id',),
            },
        ),
    ]
