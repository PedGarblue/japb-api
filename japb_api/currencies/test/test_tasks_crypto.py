from unittest.mock import patch

from django.test import TestCase

from japb_api.currencies.models import AssetKind, Currency, CurrencyConversionHistorial
from japb_api.currencies.tasks import BINANCE_SPOT, update_crypto_spot_conversions


class TestUpdateCryptoSpotConversions(TestCase):
    """Isolate from migration-seeded global cryptos; patch fetch on the tasks module."""

    def setUp(self):
        CurrencyConversionHistorial.objects.filter(
            currency_from__asset_kind=AssetKind.CRYPTO,
            currency_from__user__isnull=True,
        ).delete()
        Currency.objects.filter(
            asset_kind=AssetKind.CRYPTO,
            user__isnull=True,
        ).delete()
        self.usd = Currency.objects.create(
            name="USD", symbol="$", asset_kind=AssetKind.FIAT
        )
        self.btc = Currency.objects.create(
            name="BTC",
            symbol="₿",
            asset_kind=AssetKind.CRYPTO,
            default_conversion_source=BINANCE_SPOT,
        )

    @patch("japb_api.currencies.tasks.fetch_usdt_per_unit")
    def test_creates_historial_with_rate_one_over_price(self, mock_fetch):
        mock_fetch.return_value = 50000.0

        update_crypto_spot_conversions()

        mock_fetch.assert_called_with("BTCUSDT")
        self.assertEqual(CurrencyConversionHistorial.objects.count(), 1)
        row = CurrencyConversionHistorial.objects.get()
        self.assertEqual(row.source, BINANCE_SPOT)
        self.assertAlmostEqual(row.rate, 1.0 / 50000.0)
        self.assertEqual(row.currency_from_id, self.btc.id)
        self.assertEqual(row.currency_to_id, self.usd.id)

    @patch("japb_api.currencies.tasks.fetch_usdt_per_unit")
    def test_http_error_skips_row_without_raising(self, mock_fetch):
        mock_fetch.return_value = None

        update_crypto_spot_conversions()

        self.assertEqual(CurrencyConversionHistorial.objects.count(), 0)

    @patch("japb_api.currencies.tasks.fetch_usdt_per_unit")
    def test_partial_success_when_second_symbol_fails(self, mock_fetch):
        Currency.objects.create(
            name="ETH",
            symbol="Ξ",
            asset_kind=AssetKind.CRYPTO,
            default_conversion_source=BINANCE_SPOT,
        )

        def fake_fetch(pair):
            if pair == "BTCUSDT":
                return 50000.0
            return None

        mock_fetch.side_effect = fake_fetch

        update_crypto_spot_conversions()

        self.assertEqual(CurrencyConversionHistorial.objects.count(), 1)
        row = CurrencyConversionHistorial.objects.get()
        self.assertEqual(row.currency_from.name, "BTC")
