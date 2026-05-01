from django.db import migrations, models


def set_global_crypto_binance_spot(apps, schema_editor):
    Currency = apps.get_model("currencies", "Currency")
    CRYPTO_NAMES = ("BTC", "ETH", "SOL", "BNB", "ADA")
    Currency.objects.filter(
        name__in=CRYPTO_NAMES,
        user__isnull=True,
        asset_kind="crypto",
    ).update(default_conversion_source="binance_spot")


def revert_crypto_conversion_source(apps, schema_editor):
    Currency = apps.get_model("currencies", "Currency")
    CRYPTO_NAMES = ("BTC", "ETH", "SOL", "BNB", "ADA")
    Currency.objects.filter(
        name__in=CRYPTO_NAMES,
        user__isnull=True,
        default_conversion_source="binance_spot",
    ).update(default_conversion_source=None)


class Migration(migrations.Migration):
    dependencies = [
        ("currencies", "0012_currency_default_decimal_places"),
    ]

    operations = [
        migrations.AlterField(
            model_name="currencyconversionhistorial",
            name="source",
            field=models.CharField(
                choices=[
                    ("paralelo", "Paralelo"),
                    ("bcv", "BCV"),
                    ("binance_spot", "Binance spot (public)"),
                ],
                default="paralelo",
                max_length=100,
            ),
        ),
        migrations.RunPython(
            set_global_crypto_binance_spot,
            revert_crypto_conversion_source,
        ),
    ]
