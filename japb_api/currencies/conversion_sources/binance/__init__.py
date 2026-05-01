"""
Binance integration for currency conversion.

**Spot rates (this package, `spot.py`):** public REST endpoints such as
`/api/v3/ticker/price` — no API key. Used by the hourly Celery task to fill
`CurrencyConversionHistorial` with source `binance_spot`.

**Future P2P / user keys:** authenticated Binance APIs (e.g. P2P order history)
must live in separate modules (e.g. `p2p.py`, `signed_client.py`) backed by
per-user credentials (new model later). Do not mix signed requests into the
public spot conversion task; P2P sync is a different product surface.

For type hints, see `SpotPriceProvider`.
"""

from typing import Optional, Protocol, runtime_checkable

from japb_api.currencies.conversion_sources.binance.pairs import (
    CURRENCY_NAME_TO_BINANCE_SYMBOL,
    binance_symbol_for_currency,
)
from japb_api.currencies.conversion_sources.binance.spot import fetch_usdt_per_unit


@runtime_checkable
class SpotPriceProvider(Protocol):
    """Boundary for public spot quotes; P2P/sync uses a different interface."""

    def fetch_usdt_per_unit(self, trading_pair: str) -> Optional[float]:
        ...


__all__ = [
    "CURRENCY_NAME_TO_BINANCE_SYMBOL",
    "SpotPriceProvider",
    "binance_symbol_for_currency",
    "fetch_usdt_per_unit",
]
