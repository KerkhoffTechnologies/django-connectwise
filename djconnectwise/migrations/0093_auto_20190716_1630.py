# Generated by Django 2.1 on 2019-07-16 16:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0092_remove_ticket_work_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='automatic_email_cc',
            field=models.CharField(blank=True, max_length=1000, null=True),
        ),
        migrations.AddField(
            model_name='timeentry',
            name='email_cc',
            field=models.CharField(blank=True, max_length=1000, null=True),
        ),
    ]
