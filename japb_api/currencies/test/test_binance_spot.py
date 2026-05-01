from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from japb_api.currencies.conversion_sources.binance.spot import fetch_usdt_per_unit


class TestBinanceSpotFetch(TestCase):
    @patch("japb_api.currencies.conversion_sources.binance.spot.requests.get")
    def test_default_base_url_is_binance_us(self, mock_get: MagicMock):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"price": "50000.0"}
        mock_get.return_value = mock_response

        price = fetch_usdt_per_unit("BTCUSDT")

        mock_get.assert_called_once()
        called_url = mock_get.call_args[0][0]
        self.assertTrue(called_url.startswith("https://api.binance.us"))
        self.assertEqual(price, 50000.0)

    @override_settings(BINANCE_API_BASE_URL="https://api.binance.com")
    @patch("japb_api.currencies.conversion_sources.binance.spot.requests.get")
    def test_binance_api_base_url_setting_override(self, mock_get: MagicMock):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"price": "1.0"}
        mock_get.return_value = mock_response

        fetch_usdt_per_unit("BTCUSDT")

        called_url = mock_get.call_args[0][0]
        self.assertTrue(called_url.startswith("https://api.binance.com"))
