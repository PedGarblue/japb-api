from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("currencies", "0008_currency_default_conversion_source_seeds"),
    ]

    def add_eur_currency(apps, schema_editor):
        Currency = apps.get_model("currencies", "Currency")
        # create if not exists
        if not Currency.objects.filter(name="EUR").exists():
            Currency.objects.create(name="EUR", symbol="€")

    def remove_eur_currency(apps, schema_editor):
        Currency = apps.get_model("currencies", "Currency")
        Currency.objects.get(name="EUR").delete()

    operations = [
        migrations.RunPython(
            add_eur_currency,
            remove_eur_currency,
        ),
    ]