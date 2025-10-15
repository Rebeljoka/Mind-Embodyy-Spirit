from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0004_create_processedevent"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="stock_shortage",
            field=models.BooleanField(default=False),
        ),
    ]
