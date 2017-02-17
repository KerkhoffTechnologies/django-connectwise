# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('djconnectwise', '0009_auto_20170215_1438'),
    ]

    operations = [
        migrations.CreateModel(
            name='Team',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('team_id', models.PositiveSmallIntegerField()),
                ('name', models.CharField(max_length=30)),
                ('board', models.ForeignKey(to='djconnectwise.ConnectWiseBoard')),
                ('members', models.ManyToManyField(to='djconnectwise.Member')),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.RemoveField(
            model_name='serviceticket',
            name='team_id',
        ),
        migrations.AddField(
            model_name='company',
            name='company_id',
            field=models.PositiveSmallIntegerField(default=1),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='serviceticket',
            name='team',
            field=models.ForeignKey(blank=True, null=True, related_name='team_tickets', to='djconnectwise.Team'),
        ),
    ]
