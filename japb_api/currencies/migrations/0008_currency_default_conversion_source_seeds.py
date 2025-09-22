from django.db import migrations


def set_ves_default_conversion_source(apps, schema_editor):
    Currency = apps.get_model("currencies", "Currency")
    try:
        ves_currency = Currency.objects.get(name="VES")
        ves_currency.default_conversion_source = "paralelo"
        ves_currency.save()
    except Currency.DoesNotExist:
        # VES currency doesn't exist, skip
        pass


def revert_ves_default_conversion_source(apps, schema_editor):
    Currency = apps.get_model("currencies", "Currency")
    try:
        ves_currency = Currency.objects.get(name="VES")
        ves_currency.default_conversion_source = None
        ves_currency.save()
    except Currency.DoesNotExist:
        # VES currency doesn't exist, skip
        pass


class Migration(migrations.Migration):
    dependencies = [
        ("currencies", "0007_currency_default_conversion_source"),
    ]

    operations = [
        migrations.RunPython(
            set_ves_default_conversion_source,
            revert_ves_default_conversion_source,
        ),
    ]
