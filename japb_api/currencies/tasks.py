from japb_api.celery import app
from japb_api.currencies.models import Currency, CurrencyConversionHistorial
import japb_api.currencies.conversion_sources.ves_to_usd as ves_to_usd


@app.task
def update_currency_historial():
    rate = ves_to_usd.VesToUsd.getLatestRate()
    if rate:
        CurrencyConversionHistorial.objects.create(
            currency_from=Currency.objects.get(name="VES"),
            currency_to=Currency.objects.get(name="USD"),
            source="paralelo",
            rate=rate,
        )

    rate_bcv = ves_to_usd.VesToUsd.getLatestRateBCV()

    if rate_bcv:
        CurrencyConversionHistorial.objects.create(
            currency_from=Currency.objects.get(name="VES"),
            currency_to=Currency.objects.get(name="USD"),
            source="bcv",
            rate=rate_bcv,
        )
