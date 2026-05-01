from django.db import migrations, models


def set_crypto_default_decimal_places(apps, schema_editor):
    Currency = apps.get_model("currencies", "Currency")
    Currency.objects.filter(asset_kind="crypto").update(default_decimal_places=8)


def revert_crypto_default_decimal_places(apps, schema_editor):
    Currency = apps.get_model("currencies", "Currency")
    Currency.objects.filter(asset_kind="crypto").update(default_decimal_places=2)


class Migration(migrations.Migration):
    dependencies = [
        ("currencies", "0011_seed_crypto_currencies"),
    ]

    operations = [
        migrations.AddField(
            model_name="currency",
            name="default_decimal_places",
            field=models.PositiveSmallIntegerField(default=2),
            preserve_default=False,
        ),
        migrations.RunPython(
            set_crypto_default_decimal_places,
            revert_crypto_default_decimal_places,
        ),
    ]
