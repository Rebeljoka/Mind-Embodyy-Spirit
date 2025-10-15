from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gallery", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="stockitem",
            name="status",
            field=models.CharField(  # noqa
                choices=[
                    ('available', 'Available'),
                    ('reserved', 'Reserved'),
                    ('sold', 'Sold'),
                    ('archived', 'Archived'),
                ],
                default='available',
                max_length=16,
                db_index=True,
            ),
        ),
    ]
