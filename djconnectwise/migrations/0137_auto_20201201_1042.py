# Generated by Django 3.1.2 on 2020-12-01 10:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0136_boardstatus_time_entry_not_allowed'),
    ]

    operations = [
        migrations.AlterField(
            model_name='boardstatus',
            name='time_entry_not_allowed',
            field=models.BooleanField(null=True),
        ),
    ]