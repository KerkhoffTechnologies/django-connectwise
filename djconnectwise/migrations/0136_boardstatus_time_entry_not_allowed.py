# Generated by Django 3.1.2 on 2020-11-30 20:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0135_auto_20201016_0810'),
    ]

    operations = [
        migrations.AddField(
            model_name='boardstatus',
            name='time_entry_not_allowed',
            field=models.BooleanField(default=False),
        ),
    ]
