from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lead_validation', '0001_initial'),  # Update this to match your latest migration
    ]

    operations = [
        migrations.AddField(
            model_name='validationlog',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
    ] 