"""Map app currency codes to Binance spot symbols (USDT quote)."""

from typing import Optional

# Supported global cryptos seeded in migrations; extend when adding currencies.
CURRENCY_NAME_TO_BINANCE_SYMBOL = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "BNB": "BNBUSDT",
    "ADA": "ADAUSDT",
}


def binance_symbol_for_currency(name: str) -> Optional[str]:
    return CURRENCY_NAME_TO_BINANCE_SYMBOL.get(name)
