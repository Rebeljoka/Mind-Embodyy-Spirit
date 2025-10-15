from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0005_add_stock_shortage"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="product_status",
            field=models.CharField(max_length=16, null=True, blank=True),
        ),
    ]
