from django.test import TestCase

from japb_api.currencies.conversion_sources.binance.pairs import (
    binance_symbol_for_currency,
)


class TestBinancePairs(TestCase):
    def test_xrp_maps_to_usdt_pair(self):
        self.assertEqual(binance_symbol_for_currency("XRP"), "XRPUSDT")
