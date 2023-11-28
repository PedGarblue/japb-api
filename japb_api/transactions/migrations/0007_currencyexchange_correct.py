# Generated by Django 4.1.7 on 2023-11-26 21:02

from django.db import migrations, models
from japb_api.transactions.models import CurrencyExchange


class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0006_currencyexchange_type'),
    ]

    operations = [
        migrations.RunPython(
            # if related_transaction date is greater than exchange date
            # and the account currency is the same as the
            # related_transaction account currency, then the type is from_same_currency
            code=lambda apps, schema_editor: CurrencyExchange.objects.filter(
                related_transaction__date__gt=models.F('date'),
                account__currency=models.F('related_transaction__account__currency')
            ).update(type='from_same_currency'),
        ),
        migrations.RunPython(
            # if related_transaction date is lesser than exchange date
            # and the account currency is the same as the
            # related_transaction account currency, then the type is to_same_currency
            code=lambda apps, schema_editor: CurrencyExchange.objects.filter(
                related_transaction__date__lt=models.F('date'),
                account__currency=models.F('related_transaction__account__currency')
            ).update(type='to_same_currency'),
        ),
        migrations.RunPython(
            # if related_transaction date is greater than exchange date
            # and the account currency is different from the
            # related_transaction account currency, then the type is from_different_currency
            code=lambda apps, schema_editor: CurrencyExchange.objects.filter(
                related_transaction__date__gt=models.F('date'),
            )
            .exclude(account__currency=models.F('related_transaction__account__currency'))
            .update(type='from_different_currency'),
        ),
        migrations.RunPython(
            # if related_transaction date is lesser than exchange date
            # and the account currency is different from the
            # related_transaction account currency, then the type is to_different_currency
            code=lambda apps, schema_editor: CurrencyExchange.objects.filter(
                related_transaction__date__lt=models.F('date'),
            )
            .exclude(account__currency=models.F('related_transaction__account__currency'))
            .update(type='to_different_currency'),
        ),
    ]