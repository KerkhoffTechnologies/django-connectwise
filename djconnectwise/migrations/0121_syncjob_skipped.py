# Generated by Django 2.1.14 on 2020-08-24 13:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0120_auto_20200721_1617'),
    ]

    operations = [
        migrations.AddField(
            model_name='syncjob',
            name='skipped',
            field=models.PositiveIntegerField(null=True),
        ),
    ]
