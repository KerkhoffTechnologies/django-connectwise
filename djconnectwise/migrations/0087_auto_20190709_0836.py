# Generated by Django 2.1 on 2019-07-09 08:36

from django.db import migrations, models
import django.db.models.deletion
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0086_merge_20190507_1402'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('name', models.CharField(max_length=50)),
                ('inactive_flag', models.BooleanField(default=False)),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='ticket',
            name='work_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='work_type_tickets', to='djconnectwise.WorkType'),
        ),
        migrations.AddField(
            model_name='timeentry',
            name='work_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='djconnectwise.WorkType'),
        ),
    ]
