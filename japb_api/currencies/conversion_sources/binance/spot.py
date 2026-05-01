import logging
from typing import Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.binance.com"


def _base_url() -> str:
    return getattr(settings, "BINANCE_API_BASE_URL", DEFAULT_BASE_URL)


def fetch_usdt_per_unit(trading_pair: str, *, timeout: float = 10.0) -> Optional[float]:
    """
    Last traded price for `trading_pair` (e.g. BTCUSDT) in USDT per 1 base asset.

    Uses the public REST API; no API key. Returns None on failure.
    """
    base = _base_url().rstrip("/")
    url = f"{base}/api/v3/ticker/price"
    try:
        response = requests.get(url, params={"symbol": trading_pair}, timeout=timeout)
    except requests.RequestException as exc:
        logger.warning(
            "Binance ticker request failed for %s: %s", trading_pair, exc
        )
        return None
    if response.status_code != 200:
        logger.warning(
            "Binance ticker HTTP %s for %s: %s",
            response.status_code,
            trading_pair,
            (response.text or "")[:200],
        )
        return None
    try:
        data = response.json()
        price = float(data["price"])
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("Binance ticker parse error for %s: %s", trading_pair, exc)
        return None
    if price <= 0:
        return None
    return price
