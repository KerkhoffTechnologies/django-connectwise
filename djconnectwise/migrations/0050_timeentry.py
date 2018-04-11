# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0049_auto_20180205_1122'),
    ]

    operations = [
        migrations.CreateModel(
            name='TimeEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('charge_to_type', models.CharField(db_index=True, choices=[('ServiceTicket', 'Service Ticket'), ('ProjectTicket', 'Project Ticket'), ('ChargeCode', 'Charge Code'), ('Activity', 'Activity')], max_length=250)),
                ('billable_option', models.CharField(db_index=True, choices=[('Billable', 'Billable'), ('DoNotBill', 'Do Not Bill'), ('NoCharge', 'No Charge'), ('NoDefault', 'No Default')], max_length=250)),
                ('time_start', models.DateTimeField(null=True, blank=True)),
                ('time_end', models.DateTimeField(null=True, blank=True)),
                ('hours_deduct', models.DecimalField(null=True, max_digits=6, blank=True, decimal_places=2)),
                ('actual_hours', models.DecimalField(null=True, max_digits=6, blank=True, decimal_places=2)),
                ('notes', models.TextField(null=True, blank=True, max_length=2000)),
                ('internal_notes', models.TextField(null=True, blank=True, max_length=2000)),
                ('charge_to_id', models.ForeignKey(to='djconnectwise.Ticket')),
                ('company', models.ForeignKey(to='djconnectwise.Company')),
                ('member', models.ForeignKey(blank=True, to='djconnectwise.Member', null=True)),
            ],
        ),
    ]
