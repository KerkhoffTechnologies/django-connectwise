# Generated by Django 4.2.11 on 2024-05-21 17:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0178_alter_ticket_work_role_alter_ticket_work_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='projectphase',
            name='required_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]