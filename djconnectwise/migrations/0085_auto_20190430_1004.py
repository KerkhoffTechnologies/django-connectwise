# Generated by Django 2.0 on 2019-04-30 10:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0084_auto_20190404_1532'),
    ]

    operations = [
        migrations.AddField(
            model_name='timeentry',
            name='email_cc_flag',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='timeentry',
            name='email_contact_flag',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='timeentry',
            name='email_resource_flag',
            field=models.BooleanField(default=False),
        ),
    ]