# Generated by Django 4.0.10 on 2023-05-19 14:20

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0172_companynotetypetracker'),
    ]

    operations = [
        migrations.RenameField(
            model_name='companynotetype',
            old_name='defaultFlag',
            new_name='default_flag',
        ),
    ]
