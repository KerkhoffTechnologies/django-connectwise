# Generated by Django 4.2.11 on 2024-06-06 12:49

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0182_alter_companysite_inactive'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='temp_assets',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.TextField(), null=True, size=None),
        ),
    ]
