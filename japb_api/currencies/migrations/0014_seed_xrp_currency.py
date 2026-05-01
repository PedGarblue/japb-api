from django.db import migrations

BINANCE_SPOT = "binance_spot"


def seed_xrp(apps, schema_editor):
    Currency = apps.get_model("currencies", "Currency")
    if Currency.objects.filter(name="XRP").exists():
        Currency.objects.filter(name="XRP").update(
            asset_kind="crypto",
            default_decimal_places=8,
            default_conversion_source=BINANCE_SPOT,
        )
    else:
        Currency.objects.create(
            name="XRP",
            symbol="XRP",
            asset_kind="crypto",
            user=None,
            default_decimal_places=8,
            default_conversion_source=BINANCE_SPOT,
        )


def revert_xrp(apps, schema_editor):
    Currency = apps.get_model("currencies", "Currency")
    Currency.objects.filter(
        name="XRP", user__isnull=True, default_conversion_source=BINANCE_SPOT
    ).update(default_conversion_source=None)


class Migration(migrations.Migration):
    dependencies = [
        ("currencies", "0013_binance_spot_source_and_crypto_defaults"),
    ]

    operations = [
        migrations.RunPython(seed_xrp, revert_xrp),
    ]
