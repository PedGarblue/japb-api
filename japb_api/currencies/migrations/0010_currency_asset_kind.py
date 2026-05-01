# Generated manually for Currency.asset_kind

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("currencies", "0009_currency_add_eur"),
    ]

    operations = [
        migrations.AddField(
            model_name="currency",
            name="asset_kind",
            field=models.CharField(
                choices=[("fiat", "Fiat"), ("crypto", "Crypto")],
                db_index=True,
                default="fiat",
                max_length=20,
            ),
        ),
    ]
