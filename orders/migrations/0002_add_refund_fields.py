from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentrecord",
            name="provider_refund_id",
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="paymentrecord",
            name="refunded_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
