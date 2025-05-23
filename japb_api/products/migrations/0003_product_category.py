# Generated by Django 4.1.7 on 2024-04-07 19:08

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("transactions", "0011_currencyexchange_comissions"),
        ("products", "0002_alter_product_description_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="category",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="transactions.category",
            ),
        ),
    ]
