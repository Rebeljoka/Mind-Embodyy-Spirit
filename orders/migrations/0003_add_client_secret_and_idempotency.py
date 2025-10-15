from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_add_refund_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentrecord",
            name="provider_client_secret",
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="paymentrecord",
            name="idempotency_key",
            field=models.CharField(  # noqa
                max_length=255,
                null=True,
                blank=True,
                db_index=True,
            ),
        ),
    ]
