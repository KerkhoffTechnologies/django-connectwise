# Generated by Django 4.2.16 on 2025-04-02 16:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0189_remove_sla_calendar_remove_slapriority_priority_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='percent_complete',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
    ]
