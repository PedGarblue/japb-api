import pytz
from faker import Faker
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from ..models import Currency, CurrencyConversionHistorial
from japb_api.currencies.factories import CurrencyFactory
from japb_api.users.factories import UserFactory
from japb_api.accounts.models import Account
from japb_api.transactions.models import Transaction


class TestCurrencyViews(APITestCase):
    def setUp(self):
        self.fake = Faker(["en-US"])
        self.user = UserFactory()
        self.token = RefreshToken.for_user(self.user)
        self.data = {
            "name": "USD",
            "symbol": "$",
        }
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token.access_token}")

    def test_api_admin_can_create_currency(self):
        admin = UserFactory(is_staff=True)
        token = RefreshToken.for_user(admin)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
        self.response = self.client.post(
            reverse("currencies-list"), self.data, format="json"
        )
        self.assertEqual(self.response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Currency.objects.filter(name="USD").exists())
        self.assertEqual(Currency.objects.get(name="USD").symbol, "$")
        self.assertEqual(Currency.objects.get(name="USD").asset_kind, "fiat")
        self.assertEqual(Currency.objects.get(name="USD").default_decimal_places, 2)

    def test_api_admin_can_create_crypto_currency(self):
        admin = UserFactory(is_staff=True)
        token = RefreshToken.for_user(admin)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
        response = self.client.post(
            reverse("currencies-list"),
            {"name": "BTC", "symbol": "₿", "asset_kind": "crypto"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Currency.objects.get(name="BTC").asset_kind, "crypto")
        self.assertEqual(Currency.objects.get(name="BTC").default_decimal_places, 8)

    def test_api_currency_list_filter_by_asset_kind(self):
        Currency.objects.create(name="FILTER_FIAT", symbol="$", asset_kind="fiat")
        Currency.objects.create(
            name="FILTER_BTC",
            symbol="₿",
            asset_kind="crypto",
            default_decimal_places=8,
        )
        url = reverse("currencies-list")
        response = self.client.get(url, {"asset_kind": "crypto"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {item["name"] for item in response.json()["results"]}
        self.assertIn("FILTER_BTC", names)
        self.assertNotIn("FILTER_FIAT", names)

    def test_api_user_cannot_create_currency(self):
        initial_count = Currency.objects.count()
        self.response = self.client.post(
            reverse("currencies-list"), self.data, format="json"
        )
        self.assertEqual(self.response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Currency.objects.count(), initial_count)

    def test_api_get_currency_list(self):
        currency = CurrencyFactory()
        url = reverse("currencies-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(Currency.objects.count(), 1)
        results = response.json()["results"]
        found_currency = next((item for item in results if item["id"] == currency.id), None)
        self.assertIsNotNone(found_currency)
        self.assertEqual(found_currency["name"], currency.name)
        self.assertEqual(found_currency["symbol"], currency.symbol)
        self.assertEqual(found_currency["asset_kind"], "fiat")
        self.assertEqual(found_currency["default_decimal_places"], 2)

    """
    Returns balance of a currency
    """

    def test_api_get_currency_list_with_balance(self):
        MAIN_ACCOUNT_TRANSACTIONS_AMOUNTS = [100, 200]
        SECONDARY_ACCOUNT_TRANSACTIONS_AMOUNTS = [200, -100]
        MAIN_CURRENCY_DECIMAL_PLACES_MULTIPLIER = 100
        SUM_OF_MAIN_CURRENCY_TRANSACTIONS = (
            400 / MAIN_CURRENCY_DECIMAL_PLACES_MULTIPLIER
        )

        main_currency = Currency.objects.create(name="USD", symbol="$")
        foreign_currency, _ = Currency.objects.get_or_create(name="EUR", defaults={"symbol": "€"})

        account = Account.objects.create(
            name="Test Account", currency=main_currency, user=self.user
        )
        account_secondary = Account.objects.create(
            name="Test Account 2", currency=main_currency, user=self.user
        )
        foreign_account = Account.objects.create(
            name="Test Account 3", currency=foreign_currency, user=self.user
        )

        transactions_main = [
            Transaction(
                amount=MAIN_ACCOUNT_TRANSACTIONS_AMOUNTS[0],
                account=account,
                user=self.user,
                date=self.fake.date_time(tzinfo=pytz.UTC),
            ),
            Transaction(
                amount=MAIN_ACCOUNT_TRANSACTIONS_AMOUNTS[1],
                account=account,
                user=self.user,
                date=self.fake.date_time(tzinfo=pytz.UTC),
            ),
        ]

        transactions_secondary = [
            Transaction(
                amount=SECONDARY_ACCOUNT_TRANSACTIONS_AMOUNTS[0],
                account=account_secondary,
                user=self.user,
                date=self.fake.date_time(tzinfo=pytz.UTC),
            ),
            Transaction(
                amount=SECONDARY_ACCOUNT_TRANSACTIONS_AMOUNTS[1],
                account=account_secondary,
                user=self.user,
                date=self.fake.date_time(tzinfo=pytz.UTC),
            ),
        ]

        transactions_foreign = [
            Transaction(
                amount=100,
                account=foreign_account,
                user=self.user,
                date=self.fake.date_time(tzinfo=pytz.UTC),
            ),
        ]

        Transaction.objects.bulk_create(transactions_main)
        Transaction.objects.bulk_create(transactions_secondary)
        Transaction.objects.bulk_create(transactions_foreign)

        url = reverse("currencies-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json()["results"]
        usd_rows = [r for r in results if r["id"] == main_currency.id]
        self.assertEqual(len(usd_rows), 1)
        usd_row = usd_rows[0]
        self.assertEqual(usd_row["name"], "USD")
        self.assertEqual(usd_row["symbol"], "$")
        self.assertEqual(
            usd_row["balance"],
            "{:.2f}".format(SUM_OF_MAIN_CURRENCY_TRANSACTIONS),
        )

    def test_api_get_a_currency(self):
        currency = CurrencyFactory()

        response = self.client.get(
            reverse("currencies-detail", kwargs={"pk": currency.id}), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["name"], currency.name)
        self.assertEqual(response.json()["symbol"], currency.symbol)
        self.assertGreaterEqual(Currency.objects.count(), 1)

    def test_api_get_a_currency_with_balance(self):
        MAIN_ACCOUNT_TRANSACTIONS_AMOUNTS = [100, 200]
        SECONDARY_ACCOUNT_TRANSACTIONS_AMOUNTS = [200, -100]
        MAIN_CURRENCY_DECIMAL_PLACES_MULTIPLIER = 100
        SUM_OF_MAIN_CURRENCY_TRANSACTIONS = (
            400 / MAIN_CURRENCY_DECIMAL_PLACES_MULTIPLIER
        )

        main_currency = Currency.objects.create(name="USD", symbol="$")
        foreign_currency, _ = Currency.objects.get_or_create(name="EUR", defaults={"symbol": "€"})

        account = Account.objects.create(
            name="Test Account", currency=main_currency, user=self.user
        )
        account_secondary = Account.objects.create(
            name="Test Account 2", currency=main_currency, user=self.user
        )
        foreign_account = Account.objects.create(
            name="Test Account 3", currency=foreign_currency, user=self.user
        )

        transactions_main = [
            Transaction(
                amount=MAIN_ACCOUNT_TRANSACTIONS_AMOUNTS[0],
                account=account,
                user=self.user,
                date=self.fake.date_time(tzinfo=pytz.UTC),
            ),
            Transaction(
                amount=MAIN_ACCOUNT_TRANSACTIONS_AMOUNTS[1],
                account=account,
                user=self.user,
                date=self.fake.date_time(tzinfo=pytz.UTC),
            ),
        ]

        transactions_secondary = [
            Transaction(
                amount=SECONDARY_ACCOUNT_TRANSACTIONS_AMOUNTS[0],
                account=account_secondary,
                user=self.user,
                date=self.fake.date_time(tzinfo=pytz.UTC),
            ),
            Transaction(
                amount=SECONDARY_ACCOUNT_TRANSACTIONS_AMOUNTS[1],
                account=account_secondary,
                user=self.user,
                date=self.fake.date_time(tzinfo=pytz.UTC),
            ),
        ]

        transactions_foreign = [
            Transaction(
                amount=100,
                account=foreign_account,
                user=self.user,
                date=self.fake.date_time(tzinfo=pytz.UTC),
            ),
        ]

        Transaction.objects.bulk_create(transactions_main)
        Transaction.objects.bulk_create(transactions_secondary)
        Transaction.objects.bulk_create(transactions_foreign)

        url = reverse("currencies-detail", kwargs={"pk": main_currency.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["id"], main_currency.id)
        self.assertEqual(response.json()["name"], main_currency.name)
        self.assertEqual(response.json()["symbol"], main_currency.symbol)
        self.assertEqual(
            response.json()["balance"],
            "{:.2f}".format(SUM_OF_MAIN_CURRENCY_TRANSACTIONS),
        )

    def test_api_admin_can_update_a_currency(self):
        currency = Currency.objects.create(name="USD", symbol="$")
        admin = UserFactory(is_staff=True)
        admin_token = RefreshToken.for_user(admin)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_token.access_token}")
        new_data = {
            "name": "Super USD",
            "symbol": "$$",
        }
        response = self.client.put(
            reverse("currencies-detail", kwargs={"pk": currency.id}),
            data=new_data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        currency.refresh_from_db()
        self.assertEqual(currency.name, "Super USD")
        self.assertEqual(currency.symbol, "$$")

    def test_api_admin_can_delete_a_currency(self):
        currency = Currency.objects.create(name="USD", symbol="$")
        initial_count = Currency.objects.count()
        admin = UserFactory(is_staff=True)
        admin_token = RefreshToken.for_user(admin)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_token.access_token}")
        response = self.client.delete(
            reverse("currencies-detail", kwargs={"pk": currency.id}), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Currency.objects.count(), initial_count - 1)


class TestCurrencyConversionViews(APITestCase):
    def setUp(self):
        self.fake = Faker(["en-US"])
        self.user = UserFactory()
        self.token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token.access_token}")

        # Create required currencies
        self.usd_currency = Currency.objects.create(name="USD", symbol="$")
        self.ves_currency = Currency.objects.create(name="VES", symbol="Bs.")
        self.eur_currency, _ = Currency.objects.get_or_create(name="EUR", defaults={"symbol": "€"})

    def test_api_get_currency_conversion_with_both_rates(self):
        """Test that the endpoint returns both paralelo and bcv rates when available with gap calculation"""
        # Create conversion history for both sources
        CurrencyConversionHistorial.objects.create(
            currency_from=self.ves_currency,
            currency_to=self.usd_currency,
            source="paralelo",
            rate=260.13,
        )

        CurrencyConversionHistorial.objects.create(
            currency_from=self.ves_currency,
            currency_to=self.usd_currency,
            source="bcv",
            rate=160.12,
        )

        url = reverse("currency-conversion-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_response = {
            "VES": {
                "USD": {
                    "rates": {"bcv": 160.12, "paralelo": 260.13},
                    "gap": 38.45  # ((260.13 - 160.12) / 260.13) * 100 = 38.453, rounded to 2 places
                },
                "EUR": {
                    "rates": {}
                }
            },
        }

        self.assertEqual(response.json(), expected_response)

    def test_api_get_currency_conversion_with_only_paralelo_rate(self):
        """Test that the endpoint returns only paralelo rate when only paralelo source is available"""
        CurrencyConversionHistorial.objects.create(
            currency_from=self.ves_currency,
            currency_to=self.usd_currency,
            source="paralelo",
            rate=260.13,
        )

        url = reverse("currency-conversion-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_response = {
            "VES": {"USD": {"rates": {"paralelo": 260.13}}, "EUR": {"rates": {}}},
        }

        self.assertEqual(response.json(), expected_response)

    def test_api_get_currency_conversion_with_only_bcv_rate(self):
        """Test that the endpoint returns only bcv rate when only BCV source is available"""
        CurrencyConversionHistorial.objects.create(
            currency_from=self.ves_currency,
            currency_to=self.usd_currency,
            source="bcv",
            rate=160.12,
        )

        url = reverse("currency-conversion-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_response = {
            "VES": {"USD": {"rates": {"bcv": 160.12}}, "EUR": {"rates": {}}},
        }

        self.assertEqual(response.json(), expected_response)

    def test_api_get_currency_conversion_with_no_rates(self):
        """Test that the endpoint returns empty rates object when no conversion rates exist"""
        url = reverse("currency-conversion-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_response = {
            "VES": {"USD": {"rates": {}}, "EUR": {"rates": {}}},
        }

        self.assertEqual(response.json(), expected_response)

    def test_api_get_currency_conversion_missing_usd_currency(self):
        """Test that the endpoint handles missing USD currency gracefully"""
        # Delete USD currency
        self.usd_currency.delete()

        url = reverse("currency-conversion-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_response = {
            "VES": {"USD": {"rates": {}}, "EUR": {"rates": {}}},
        }

        self.assertEqual(response.json(), expected_response)

    def test_api_get_currency_conversion_missing_ves_currency(self):
        """Test that the endpoint handles missing VES currency gracefully"""
        # Delete VES currency
        self.ves_currency.delete()

        url = reverse("currency-conversion-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_response = {
            "VES": {"USD": {"rates": {}}, "EUR": {"rates": {}}},
        }

        self.assertEqual(response.json(), expected_response)

    def test_api_get_currency_conversion_gap_not_included_with_single_rate(self):
        """Test that gap is not included when only one rate is available"""
        CurrencyConversionHistorial.objects.create(
            currency_from=self.ves_currency,
            currency_to=self.usd_currency,
            source="paralelo",
            rate=260.13,
        )

        url = reverse("currency-conversion-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        response_data = response.json()
        self.assertNotIn("gap", response_data["VES"]["USD"])
        self.assertEqual(response_data["VES"]["USD"]["rates"]["paralelo"], 260.13)
        # EUR should be present but empty
        self.assertEqual(response_data["VES"]["EUR"]["rates"], {})

    def test_api_get_currency_conversion_latest_rates_only(self):
        """Test that the endpoint returns only the latest rates when multiple exist"""
        from datetime import timedelta
        from django.utils import timezone

        # Create older conversion rates
        old_date = timezone.now() - timedelta(days=1)
        CurrencyConversionHistorial.objects.create(
            currency_from=self.ves_currency,
            currency_to=self.usd_currency,
            source="paralelo",
            rate=250.00,
        )
        # Manually set older date
        old_paralelo = CurrencyConversionHistorial.objects.filter(
            source="paralelo"
        ).first()
        old_paralelo.date = old_date
        old_paralelo.save()

        CurrencyConversionHistorial.objects.create(
            currency_from=self.ves_currency,
            currency_to=self.usd_currency,
            source="bcv",
            rate=150.00,
        )
        # Manually set older date
        old_bcv = CurrencyConversionHistorial.objects.filter(source="bcv").first()
        old_bcv.date = old_date
        old_bcv.save()

        # Create newer conversion rates
        CurrencyConversionHistorial.objects.create(
            currency_from=self.ves_currency,
            currency_to=self.usd_currency,
            source="paralelo",
            rate=260.13,
        )

        CurrencyConversionHistorial.objects.create(
            currency_from=self.ves_currency,
            currency_to=self.usd_currency,
            source="bcv",
            rate=160.12,
        )

        url = reverse("currency-conversion-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_response = {
            "VES": {
                "USD": {
                    "rates": {"bcv": 160.12, "paralelo": 260.13},
                    "gap": 38.45  # ((260.13 - 160.12) / 260.13) * 100 = 38.453, rounded to 2 places
                },
                "EUR": {
                    "rates": {}
                }
            },
        }

        self.assertEqual(response.json(), expected_response)

    def test_api_get_currency_conversion_with_eur_bcv_rate(self):
        """Test that the endpoint returns VES to EUR BCV rate when available"""
        CurrencyConversionHistorial.objects.create(
            currency_from=self.ves_currency,
            currency_to=self.eur_currency,
            source="bcv",
            rate=210.12,
        )

        url = reverse("currency-conversion-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_response = {
            "VES": {
                "USD": {"rates": {}},
                "EUR": {"rates": {"bcv": 210.12}}
            }
        }

        self.assertEqual(response.json(), expected_response)

    def test_api_get_currency_conversion_eur_gap_not_included_without_paralelo(self):
        """Test that EUR gap is not included when paralelo USD rate is not available"""
        # Only create VES to EUR conversion, no paralelo USD rate
        CurrencyConversionHistorial.objects.create(
            currency_from=self.ves_currency,
            currency_to=self.eur_currency,
            source="bcv",
            rate=210.12,
        )

        url = reverse("currency-conversion-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        response_data = response.json()
        self.assertNotIn("gap", response_data["VES"]["EUR"])
        self.assertEqual(response_data["VES"]["EUR"]["rates"]["bcv"], 210.12)

    def test_api_get_currency_conversion_with_both_ves_and_eur_rates(self):
        """Test that the endpoint returns both VES to USD and VES to EUR rates when available"""
        # Create VES to USD conversions
        CurrencyConversionHistorial.objects.create(
            currency_from=self.ves_currency,
            currency_to=self.usd_currency,
            source="paralelo",
            rate=260.13,
        )
        CurrencyConversionHistorial.objects.create(
            currency_from=self.ves_currency,
            currency_to=self.usd_currency,
            source="bcv",
            rate=160.12,
        )

        # Create VES to EUR conversion
        CurrencyConversionHistorial.objects.create(
            currency_from=self.ves_currency,
            currency_to=self.eur_currency,
            source="bcv",
            rate=210.12,
        )

        url = reverse("currency-conversion-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_response = {
            "VES": {
                "USD": {
                    "rates": {"bcv": 160.12, "paralelo": 260.13},
                    "gap": 38.45
                },
                "EUR": {
                    "rates": {"bcv": 210.12},
                    "gap": 19.23  # ((260.13 - 210.12) / 260.13) * 100 = 19.23
                }
            }
        }

        self.assertEqual(response.json(), expected_response)

    def test_api_get_currency_conversion_missing_eur_currency(self):
        """Test that the endpoint handles missing EUR currency gracefully"""
        # Delete EUR currency
        self.eur_currency.delete()

        url = reverse("currency-conversion-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_response = {
            "VES": {
                "USD": {"rates": {}},
                "EUR": {"rates": {}}
            }
        }

        self.assertEqual(response.json(), expected_response)