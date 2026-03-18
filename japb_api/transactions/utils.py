from japb_api.currencies.models import CurrencyConversionHistorial
from .models import CurrencyExchange, ExchangeComission


def convert_transaction_to_usd(transaction, usd_currency):
    """
    Convert a transaction amount to USD.
    Returns (usd_amount, error_info).
    On success: (float, None). On failure: (None, dict with error details).
    """
    if transaction.account.currency.name == "USD":
        return transaction.amount / (10 ** transaction.account.decimal_places), None

    if transaction.to_main_currency_amount is not None:
        return transaction.to_main_currency_amount / 100.0, None

    conversion = (
        CurrencyConversionHistorial.objects.filter(
            currency_from=transaction.account.currency,
            currency_to=usd_currency,
            source=transaction.account.currency.default_conversion_source,
            date__lte=transaction.date,
        )
        .order_by("-date")
        .first()
    )

    if conversion:
        amount_float = transaction.amount / (10 ** transaction.account.decimal_places)
        return amount_float / conversion.rate, None

    return None, {
        "id": transaction.id,
        "description": transaction.description,
        "date": transaction.date.isoformat(),
        "amount": transaction.amount / (10 ** transaction.account.decimal_places),
        "currency": transaction.account.currency.name,
        "reason": "No conversion rate available",
    }


def should_skip_transaction(transaction):
    """
    Returns True if the transaction is a profit or currency exchange
    and should be excluded from expense aggregation.
    """
    try:
        commission = transaction.exchangecomission
        if commission.type != "comission":
            return True
    except ExchangeComission.DoesNotExist:
        pass

    try:
        transaction.currencyexchange
        return True
    except CurrencyExchange.DoesNotExist:
        pass

    return False
