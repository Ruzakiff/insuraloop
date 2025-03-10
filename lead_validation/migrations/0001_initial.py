# Generated by Django 5.1.7 on 2025-03-08 19:14

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('lead_capture', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ValidationSetting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('high_quality_threshold', models.IntegerField(default=80, help_text='Minimum score for high quality leads')),
                ('medium_quality_threshold', models.IntegerField(default=50, help_text='Minimum score for medium quality leads')),
                ('email_weight', models.IntegerField(default=40, help_text='Maximum points for email validation')),
                ('phone_weight', models.IntegerField(default=30, help_text='Maximum points for phone validation')),
                ('location_weight', models.IntegerField(default=15, help_text='Maximum points for location validation')),
                ('name_weight', models.IntegerField(default=15, help_text='Maximum points for name validation')),
                ('disposable_domains', models.TextField(blank=True, help_text='Comma-separated list of disposable email domains to block')),
                ('reject_disposable_emails', models.BooleanField(default=True)),
                ('reject_invalid_phones', models.BooleanField(default=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='ValidationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('score', models.IntegerField(default=0)),
                ('details', models.JSONField(blank=True, default=dict)),
                ('lead', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='validation_logs', to='lead_capture.lead')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
