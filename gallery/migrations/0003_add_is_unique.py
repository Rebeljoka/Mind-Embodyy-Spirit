from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gallery", "0002_add_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="stockitem",
            name="is_unique",
            field=models.BooleanField(default=False, help_text="If true, item is single-copy and uses status transitions instead of stock counts"),
        ),
    ]
