# Generated by Django 3.1.2 on 2021-01-08 12:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0142_contactcommunication_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='contactcommunication',
            name='default_flag',
            field=models.BooleanField(blank=True, null=True),
        ),
    ]
