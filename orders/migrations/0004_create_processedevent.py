from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0003_add_client_secret_and_idempotency"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProcessedEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ("provider", models.CharField(max_length=64)),
                ("event_id", models.CharField(max_length=255, unique=True)),
                ("payload", models.JSONField(null=True, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
