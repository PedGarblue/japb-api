# Generated by Django 4.1.7 on 2023-11-30 23:08

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("transactions", "0008_currencyexchange_correct"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExchangeComission",
            fields=[
                (
                    "transaction_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="transactions.transaction",
                    ),
                ),
                (
                    "type",
                    models.CharField(
                        choices=[("comission", "comission"), ("profit", "profit")],
                        default="comission",
                        max_length=50,
                    ),
                ),
                (
                    "exchange_from",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="exchange_from",
                        to="transactions.currencyexchange",
                    ),
                ),
                (
                    "exchange_to",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="exchange_to",
                        to="transactions.currencyexchange",
                    ),
                ),
            ],
            bases=("transactions.transaction",),
        ),
    ]
