# Generated by Django 2.1 on 2019-05-06 09:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0085_auto_20190503_1546'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='actual_end',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='project',
            name='actual_start',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='project',
            name='estimated_end',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='project',
            name='estimated_start',
            field=models.DateField(blank=True, null=True),
        ),
    ]
