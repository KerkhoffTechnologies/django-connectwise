# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0049_auto_20180205_1122'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompanyType',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, verbose_name='ID', serialize=False)),
                ('name', models.CharField(max_length=50)),
                ('vendor_flag', models.BooleanField()),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.RemoveField(
            model_name='company',
            name='type',
        ),
        migrations.AddField(
            model_name='company',
            name='company_type',
            field=models.ForeignKey(blank=True, null=True, to='djconnectwise.CompanyType'),
        ),
    ]
