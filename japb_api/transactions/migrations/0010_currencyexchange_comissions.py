# Generated by Django 4.1.7 on 2023-11-26 21:02

from django.db import migrations, models
from japb_api.transactions.models import CurrencyExchange, ExchangeComission
from django.db.models import F, Subquery

class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0009_exchangecomission'),
    ]

    operations = [
        migrations.RunPython(
            code=lambda apps, schema_editor: [
                # create comission transactions for the updated currency exchanges
                ExchangeComission.objects.create(
                    # amount is negative and the related_transaction amount is positive
                    amount=currency_exchange.amount + currency_exchange.related_transaction.amount,
                    account=currency_exchange.account,
                    description=f'Comission for [{currency_exchange.description}]',
                    date=currency_exchange.date,
                    exchange_from=currency_exchange,
                    exchange_to=currency_exchange.related_transaction,
                )
                for currency_exchange in CurrencyExchange.objects.filter(
                    type='from_same_currency',
                    amount__lt=-models.F('related_transaction__amount')
                )
            ],
            reverse_code=lambda apps, schema_editor: [
                # delete the created comission transactions
                ExchangeComission.objects.filter(
                    exchange_from__type='from_same_currency',
                    exchange_from__amount__lt=-models.F('exchange_to__amount')
                ).delete()
            ]
        ),
    ]
