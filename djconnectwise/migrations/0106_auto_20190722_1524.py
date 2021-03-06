# Generated by Django 2.1 on 2019-07-22 15:24

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0105_auto_20190722_1444'),
    ]

    operations = [
        migrations.AddField(
            model_name='activity',
            name='agreement',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='djconnectwise.Agreement'),
        ),
        migrations.AddField(
            model_name='activity',
            name='company',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='djconnectwise.Company'),
        ),
    ]
