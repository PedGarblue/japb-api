from django.db import migrations


def seed_crypto_currencies(apps, schema_editor):
    Currency = apps.get_model("currencies", "Currency")

    Currency.objects.filter(name="BTC").update(asset_kind="crypto")

    cryptos = [
        ("ETH", "Ξ"),
        ("SOL", "SOL"),
        ("BNB", "BNB"),
        ("ADA", "ADA"),
    ]
    for name, symbol in cryptos:
        if Currency.objects.filter(name=name).exists():
            Currency.objects.filter(name=name).update(asset_kind="crypto")
        else:
            Currency.objects.create(
                name=name,
                symbol=symbol,
                asset_kind="crypto",
                user=None,
                default_conversion_source=None,
            )


def unseed_crypto_currencies(apps, schema_editor):
    """Only revert BTC; do not delete seeded coins (may be referenced by accounts)."""
    Currency = apps.get_model("currencies", "Currency")
    Currency.objects.filter(name="BTC").update(asset_kind="fiat")


class Migration(migrations.Migration):
    dependencies = [
        ("currencies", "0010_currency_asset_kind"),
    ]

    operations = [
        migrations.RunPython(seed_crypto_currencies, unseed_crypto_currencies),
    ]
