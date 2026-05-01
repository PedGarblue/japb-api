from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("transactions", "0013_transactionitem"),
    ]

    operations = [
        migrations.AlterField(
            model_name="transaction",
            name="amount",
            field=models.BigIntegerField(),
        ),
        migrations.AlterField(
            model_name="transaction",
            name="to_main_currency_amount",
            field=models.BigIntegerField(null=True),
        ),
        migrations.AlterField(
            model_name="transactionitem",
            name="quantity",
            field=models.BigIntegerField(default=0, validators=[MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name="transactionitem",
            name="price",
            field=models.BigIntegerField(null=True),
        ),
        migrations.AlterField(
            model_name="transactionitem",
            name="total_price",
            field=models.BigIntegerField(null=True),
        ),
    ]
