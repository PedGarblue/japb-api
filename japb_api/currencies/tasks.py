import logging

from japb_api.celery import app
from japb_api.currencies.conversion_sources.binance import (
    binance_symbol_for_currency,
    fetch_usdt_per_unit,
)
import japb_api.currencies.conversion_sources.ves_to_eur as ves_to_eur
import japb_api.currencies.conversion_sources.ves_to_usd as ves_to_usd
from japb_api.currencies.models import (
    AssetKind,
    Currency,
    CurrencyConversionHistorial,
)

logger = logging.getLogger(__name__)

BINANCE_SPOT = "binance_spot"


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
        print("VES to USD from Paralelo: Bs.{rate}")
    else:
        print("No rate found for VES to USD from paralelo source")

    rate_bcv = ves_to_usd.VesToUsd.getLatestRateBCV()

    if rate_bcv:
        CurrencyConversionHistorial.objects.create(
            currency_from=Currency.objects.get(name="VES"),
            currency_to=Currency.objects.get(name="USD"),
            source="bcv",
            rate=rate_bcv,
        )
        print("VES to USD from BCV: Bs.{rate_bcv}")
    else:
        print("No rate found for VES to USD from BCV source")

    rate_bcv_eur = ves_to_eur.VesToEur.getLatestRateBCV()

    if rate_bcv_eur:
        CurrencyConversionHistorial.objects.create(
            currency_from=Currency.objects.get(name="VES"),
            currency_to=Currency.objects.get(name="EUR"),
            source="bcv",
            rate=rate_bcv_eur,
        )
        print("VES to EUR from BCV: €{rate_bcv_eur}")
    else:
        print("No rate found for VES to EUR from BCV source")


@app.task
def update_crypto_spot_conversions():
    """
    Fetch public Binance spot USDT prices and append historial rows.
    Schedule: hourly (see celery beat). Uses UTC.
    """
    try:
        usd = Currency.objects.get(name="USD")
    except Currency.DoesNotExist:
        logger.error("USD currency missing; skipping crypto spot conversion update")
        return

    for currency in Currency.objects.filter(
        asset_kind=AssetKind.CRYPTO,
        default_conversion_source=BINANCE_SPOT,
        user__isnull=True,
    ).order_by("name"):
        pair = binance_symbol_for_currency(currency.name)
        if not pair:
            logger.debug("No Binance USDT pair mapped for currency %s", currency.name)
            continue
        usdt_per_unit = fetch_usdt_per_unit(pair)
        if usdt_per_unit is None:
            continue
        rate = 1.0 / usdt_per_unit
        CurrencyConversionHistorial.objects.create(
            currency_from=currency,
            currency_to=usd,
            source=BINANCE_SPOT,
            rate=rate,
        )
