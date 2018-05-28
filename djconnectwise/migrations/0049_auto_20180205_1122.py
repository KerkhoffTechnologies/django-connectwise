# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0048_project_manager'),
    ]

    operations = [
        migrations.CreateModel(
            name='SalesProbability',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('probability', models.IntegerField()),
            ],
            options={
                'ordering': ('probability',),
                'verbose_name_plural': 'Sales probabilities',
            },
        ),
        migrations.AddField(
            model_name='opportunity',
            name='probability',
            field=models.ForeignKey(null=True, to='djconnectwise.SalesProbability', blank=True, related_name='sales_probability', on_delete=models.CASCADE),
        ),
    ]
