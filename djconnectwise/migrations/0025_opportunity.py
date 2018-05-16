# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0025_opportunitypriority'),
    ]

    operations = [
        migrations.CreateModel(
            name='Opportunity',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(max_length=100)),
                ('expected_close_date', models.DateField()),
                ('notes', models.TextField()),
                ('source', models.CharField(max_length=100)),
                ('location_id', models.IntegerField()),
                ('business_unit_id', models.IntegerField()),
                ('customer_po', models.CharField(max_length=100, blank=True, null=True)),
                ('pipeline_change_date', models.DateTimeField(blank=True, null=True)),
                ('date_became_lead', models.DateTimeField(blank=True, null=True)),
                ('closed_date', models.DateTimeField(blank=True, null=True)),
                ('closed_by', models.ForeignKey(blank=True, null=True, related_name='opportunity_closed_by', to='djconnectwise.Member', on_delete=models.SET_NULL)),
                ('company', models.ForeignKey(blank=True, null=True, to='djconnectwise.Company', on_delete=models.SET_NULL)),
                ('primary_sales_rep', models.ForeignKey(blank=True, null=True, related_name='opportunity_primary', to='djconnectwise.Member', on_delete=models.SET_NULL)),
                ('priority', models.ForeignKey(to='djconnectwise.OpportunityPriority', on_delete=models.CASCADE)),
                ('secondary_sales_rep', models.ForeignKey(blank=True, null=True, related_name='opportunity_secondary', to='djconnectwise.Member', on_delete=models.SET_NULL)),
                ('stage', models.ForeignKey(to='djconnectwise.OpportunityStage', on_delete=models.CASCADE)),
                ('status', models.ForeignKey(blank=True, null=True, to='djconnectwise.OpportunityStatus', on_delete=models.SET_NULL)),
                ('type', models.ForeignKey(blank=True, null=True, to='djconnectwise.OpportunityType', on_delete=models.SET_NULL)),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
    ]
