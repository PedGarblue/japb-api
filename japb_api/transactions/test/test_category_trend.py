import pytz
from datetime import datetime, timedelta
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from ..models import Transaction, CurrencyExchange, ExchangeComission, Category
from japb_api.users.models import User
from japb_api.accounts.models import Account
from japb_api.currencies.models import Currency, CurrencyConversionHistorial


class TestCategoryTrendViewSet(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        self.token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token.access_token}")

        self.usd_currency = Currency.objects.create(name="USD", default_conversion_source="paralelo")
        self.ves_currency = Currency.objects.create(name="VES", default_conversion_source="paralelo")
        self.eur_currency = Currency.objects.create(name="EUR", default_conversion_source="paralelo")

        self.usd_account = Account.objects.create(
            name="USD Account", currency=self.usd_currency, decimal_places=2, user=self.user,
        )
        self.ves_account = Account.objects.create(
            name="VES Account", currency=self.ves_currency, decimal_places=2, user=self.user,
        )
        self.eur_account = Account.objects.create(
            name="EUR Account", currency=self.eur_currency, decimal_places=2, user=self.user,
        )

        rate_date = datetime(2024, 1, 1, tzinfo=pytz.UTC)
        self.ves_to_usd = CurrencyConversionHistorial.objects.create(
            currency_from=self.ves_currency, currency_to=self.usd_currency,
            rate=60.0, source="paralelo", user=None,
        )
        self.ves_to_usd.date = rate_date
        self.ves_to_usd.save()

        self.eur_to_usd = CurrencyConversionHistorial.objects.create(
            currency_from=self.eur_currency, currency_to=self.usd_currency,
            rate=1.1, source="paralelo", user=None,
        )
        self.eur_to_usd.date = rate_date
        self.eur_to_usd.save()

        self.parent_category = Category.objects.create(
            name="Food", color="#000000", description="Food expenses",
            type="expense", user=None,
        )
        self.child_groceries = Category.objects.create(
            name="Groceries", color="#111111", description="Groceries",
            type="expense", parent_category=self.parent_category, user=None,
        )
        self.child_restaurants = Category.objects.create(
            name="Restaurants", color="#222222", description="Restaurants",
            type="expense", parent_category=self.parent_category, user=None,
        )
        self.other_category = Category.objects.create(
            name="Transportation", color="#333333", description="Transport",
            type="expense", user=None,
        )

        self.url = reverse("category-trend-list")

    def _make_tx(self, amount, category, date_str, account=None):
        """Helper to create a transaction. amount in float (e.g. -50.0)."""
        acct = account or self.usd_account
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=12, tzinfo=pytz.UTC)
        return Transaction.objects.create(
            user=self.user, account=acct,
            amount=int(amount * (10 ** acct.decimal_places)),
            description="test", date=dt, category=category,
        )

    # --- Monthly granularity ---

    def test_monthly_granularity_basic(self):
        self._make_tx(-50, self.parent_category, "2025-01-15")
        self._make_tx(-30, self.parent_category, "2025-02-10")
        self._make_tx(-20, self.parent_category, "2025-03-05")

        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "2025-01-01",
            "end_date": "2025-03-31",
            "granularity": "monthly",
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["granularity"], "monthly")
        self.assertEqual(len(data["periods"]), 3)
        self.assertEqual(data["periods"][0]["label"], "2025-01")
        self.assertEqual(data["periods"][0]["total_amount_usd"], 50.0)
        self.assertEqual(data["periods"][1]["label"], "2025-02")
        self.assertEqual(data["periods"][1]["total_amount_usd"], 30.0)
        self.assertEqual(data["periods"][2]["label"], "2025-03")
        self.assertEqual(data["periods"][2]["total_amount_usd"], 20.0)
        self.assertEqual(data["grand_total_usd"], 100.0)

    def test_monthly_default_granularity(self):
        self._make_tx(-50, self.parent_category, "2025-01-15")

        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["granularity"], "monthly")

    # --- Weekly granularity ---

    def test_weekly_granularity_basic(self):
        # 2025-01-06 is a Monday
        self._make_tx(-40, self.parent_category, "2025-01-07")  # Tue, week of Jan 6
        self._make_tx(-25, self.parent_category, "2025-01-14")  # Tue, week of Jan 13

        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "2025-01-06",
            "end_date": "2025-01-19",
            "granularity": "weekly",
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["granularity"], "weekly")
        self.assertEqual(len(data["periods"]), 2)
        self.assertEqual(data["periods"][0]["label"], "2025-W02")
        self.assertEqual(data["periods"][0]["total_amount_usd"], 40.0)
        self.assertEqual(data["periods"][1]["label"], "2025-W03")
        self.assertEqual(data["periods"][1]["total_amount_usd"], 25.0)

    # --- Category aggregation ---

    def test_aggregates_parent_and_children(self):
        self._make_tx(-50, self.parent_category, "2025-01-15")
        self._make_tx(-30, self.child_groceries, "2025-01-20")
        self._make_tx(-20, self.child_restaurants, "2025-01-25")

        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
        })

        data = response.json()
        self.assertEqual(data["periods"][0]["total_amount_usd"], 100.0)

    def test_per_child_breakdown(self):
        self._make_tx(-50, self.parent_category, "2025-01-15")
        self._make_tx(-30, self.child_groceries, "2025-01-20")
        self._make_tx(-20, self.child_restaurants, "2025-01-25")

        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
        })

        data = response.json()
        children = data["periods"][0]["children"]
        self.assertEqual(len(children), 2)
        names = {c["category_name"] for c in children}
        self.assertEqual(names, {"Groceries", "Restaurants"})
        groceries = next(c for c in children if c["category_name"] == "Groceries")
        restaurants = next(c for c in children if c["category_name"] == "Restaurants")
        self.assertEqual(groceries["total_amount_usd"], 30.0)
        self.assertEqual(restaurants["total_amount_usd"], 20.0)

    def test_parent_transactions_not_in_children_breakdown(self):
        """Transactions tagged directly on the parent appear in total but not children."""
        self._make_tx(-50, self.parent_category, "2025-01-15")

        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
        })

        data = response.json()
        self.assertEqual(data["periods"][0]["total_amount_usd"], 50.0)
        self.assertEqual(data["periods"][0]["children"], [])

    # --- Empty periods ---

    def test_empty_periods_included(self):
        self._make_tx(-50, self.parent_category, "2025-01-15")

        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "2025-01-01",
            "end_date": "2025-03-31",
        })

        data = response.json()
        self.assertEqual(len(data["periods"]), 3)
        self.assertEqual(data["periods"][0]["total_amount_usd"], 50.0)
        self.assertEqual(data["periods"][1]["total_amount_usd"], 0.0)
        self.assertEqual(data["periods"][1]["children"], [])
        self.assertEqual(data["periods"][2]["total_amount_usd"], 0.0)

    # --- Validation ---

    def test_missing_category_returns_400(self):
        response = self.client.get(self.url, {
            "start_date": "2025-01-01", "end_date": "2025-01-31",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_dates_returns_400(self):
        response = self.client.get(self.url, {
            "category": self.parent_category.id,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_category_returns_404(self):
        response = self.client.get(self.url, {
            "category": 99999,
            "start_date": "2025-01-01", "end_date": "2025-01-31",
        })
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_invalid_granularity_returns_400(self):
        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "2025-01-01", "end_date": "2025-01-31",
            "granularity": "daily",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_start_after_end_returns_400(self):
        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "2025-03-01", "end_date": "2025-01-01",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_date_format_returns_400(self):
        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "01-01-2025", "end_date": "2025-01-31",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- User isolation ---

    def test_only_user_transactions(self):
        other_user = User.objects.create_user(
            email="other@example.com", username="other", password="pass123",
        )
        Transaction.objects.create(
            user=other_user, account=self.usd_account, amount=-5000,
            description="other", date=datetime(2025, 1, 15, 12, tzinfo=pytz.UTC),
            category=self.parent_category,
        )
        self._make_tx(-30, self.parent_category, "2025-01-15")

        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "2025-01-01", "end_date": "2025-01-31",
        })

        data = response.json()
        self.assertEqual(data["periods"][0]["total_amount_usd"], 30.0)

    def test_unauthorized_returns_401(self):
        self.client.credentials()
        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "2025-01-01", "end_date": "2025-01-31",
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- Currency conversion ---

    def test_usd_direct_conversion(self):
        self._make_tx(-50, self.parent_category, "2025-01-15")

        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "2025-01-01", "end_date": "2025-01-31",
        })
        self.assertEqual(response.json()["periods"][0]["total_amount_usd"], 50.0)

    def test_to_main_currency_amount_conversion(self):
        dt = datetime(2025, 1, 15, 12, tzinfo=pytz.UTC)
        Transaction.objects.create(
            user=self.user, account=self.ves_account,
            amount=-60000, to_main_currency_amount=-1000,
            description="ves", date=dt, category=self.parent_category,
        )

        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "2025-01-01", "end_date": "2025-01-31",
        })
        self.assertEqual(response.json()["periods"][0]["total_amount_usd"], 10.0)

    def test_historial_conversion(self):
        self._make_tx(-600, self.parent_category, "2025-01-15", account=self.ves_account)

        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "2025-01-01", "end_date": "2025-01-31",
        })
        # 600 VES / 60.0 rate = 10 USD
        self.assertEqual(response.json()["periods"][0]["total_amount_usd"], 10.0)

    def test_malformed_transactions(self):
        unknown = Currency.objects.create(name="UNKNOWN", default_conversion_source="paralelo")
        unknown_acct = Account.objects.create(
            name="Unknown", currency=unknown, decimal_places=2, user=self.user,
        )
        self._make_tx(-50, self.parent_category, "2025-01-15", account=unknown_acct)

        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "2025-01-01", "end_date": "2025-01-31",
        })

        data = response.json()
        self.assertEqual(data["periods"][0]["total_amount_usd"], 0.0)
        self.assertEqual(len(data["malformed_transactions"]), 1)
        self.assertEqual(data["malformed_transactions"][0]["currency"], "UNKNOWN")

    # --- Exchange / commission filtering ---

    def test_excludes_currency_exchanges(self):
        CurrencyExchange.objects.create(
            user=self.user, account=self.usd_account, amount=-5000,
            description="exchange", date=datetime(2025, 1, 15, 12, tzinfo=pytz.UTC),
            type="from_same_currency", category=self.parent_category,
        )
        self._make_tx(-30, self.parent_category, "2025-01-15")

        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "2025-01-01", "end_date": "2025-01-31",
        })
        self.assertEqual(response.json()["periods"][0]["total_amount_usd"], 30.0)

    def test_includes_commissions(self):
        exchange_from = CurrencyExchange.objects.create(
            user=self.user, account=self.usd_account, amount=-10000,
            description="from", date=datetime(2025, 1, 15, 12, tzinfo=pytz.UTC),
            type="from_same_currency", category=None,
        )
        exchange_to = CurrencyExchange.objects.create(
            user=self.user, account=self.usd_account, amount=9500,
            description="to", date=datetime(2025, 1, 15, 12, tzinfo=pytz.UTC),
            type="to_same_currency", category=None,
        )
        ExchangeComission.objects.create(
            user=self.user, account=self.usd_account, amount=-500,
            description="commission", date=datetime(2025, 1, 15, 12, tzinfo=pytz.UTC),
            type="comission", exchange_from=exchange_from, exchange_to=exchange_to,
            category=self.parent_category,
        )
        self._make_tx(-30, self.parent_category, "2025-01-15")

        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "2025-01-01", "end_date": "2025-01-31",
        })
        # 5.00 commission + 30.00 expense = 35.00
        self.assertEqual(response.json()["periods"][0]["total_amount_usd"], 35.0)

    def test_excludes_profits(self):
        exchange_from = CurrencyExchange.objects.create(
            user=self.user, account=self.usd_account, amount=-10000,
            description="from", date=datetime(2025, 1, 15, 12, tzinfo=pytz.UTC),
            type="from_same_currency", category=None,
        )
        exchange_to = CurrencyExchange.objects.create(
            user=self.user, account=self.usd_account, amount=10500,
            description="to", date=datetime(2025, 1, 15, 12, tzinfo=pytz.UTC),
            type="to_same_currency", category=None,
        )
        ExchangeComission.objects.create(
            user=self.user, account=self.usd_account, amount=500,
            description="profit", date=datetime(2025, 1, 15, 12, tzinfo=pytz.UTC),
            type="profit", exchange_from=exchange_from, exchange_to=exchange_to,
            category=self.parent_category,
        )

        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "2025-01-01", "end_date": "2025-01-31",
        })
        self.assertEqual(response.json()["periods"][0]["total_amount_usd"], 0.0)

    # --- exclude_categories ---

    def test_exclude_categories(self):
        self._make_tx(-50, self.parent_category, "2025-01-15")
        self._make_tx(-30, self.child_groceries, "2025-01-15")
        self._make_tx(-20, self.child_restaurants, "2025-01-15")

        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
            "exclude_categories": str(self.child_restaurants.id),
        })

        data = response.json()
        # Parent (50) + Groceries (30) = 80, Restaurants excluded
        self.assertEqual(data["periods"][0]["total_amount_usd"], 80.0)
        children_names = [c["category_name"] for c in data["periods"][0]["children"]]
        self.assertIn("Groceries", children_names)
        self.assertNotIn("Restaurants", children_names)

    def test_exclude_multiple_categories(self):
        self._make_tx(-50, self.parent_category, "2025-01-15")
        self._make_tx(-30, self.child_groceries, "2025-01-15")
        self._make_tx(-20, self.child_restaurants, "2025-01-15")

        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
            "exclude_categories": f"{self.child_groceries.id},{self.child_restaurants.id}",
        })

        data = response.json()
        self.assertEqual(data["periods"][0]["total_amount_usd"], 50.0)
        self.assertEqual(data["periods"][0]["children"], [])

    # --- include_categories ---

    def test_include_external_categories(self):
        self._make_tx(-50, self.parent_category, "2025-01-15")
        self._make_tx(-25, self.other_category, "2025-01-20")

        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
            "include_categories": str(self.other_category.id),
        })

        data = response.json()
        self.assertEqual(data["periods"][0]["total_amount_usd"], 75.0)
        children = data["periods"][0]["children"]
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0]["category_name"], "Transportation")
        self.assertEqual(children[0]["total_amount_usd"], 25.0)

    def test_include_nonexistent_category_returns_404(self):
        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
            "include_categories": "99999",
        })
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- Combined exclude + include ---

    def test_exclude_and_include_together(self):
        self._make_tx(-50, self.parent_category, "2025-01-15")
        self._make_tx(-30, self.child_groceries, "2025-01-15")
        self._make_tx(-20, self.child_restaurants, "2025-01-15")
        self._make_tx(-10, self.other_category, "2025-01-15")

        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
            "exclude_categories": str(self.child_restaurants.id),
            "include_categories": str(self.other_category.id),
        })

        data = response.json()
        # Parent(50) + Groceries(30) + Transportation(10) = 90
        self.assertEqual(data["periods"][0]["total_amount_usd"], 90.0)
        children_names = {c["category_name"] for c in data["periods"][0]["children"]}
        self.assertEqual(children_names, {"Groceries", "Transportation"})

    # --- Period boundaries ---

    def test_monthly_period_clipping(self):
        """start_date/end_date mid-month should clip period_start/period_end."""
        self._make_tx(-50, self.parent_category, "2025-01-20")

        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "2025-01-15",
            "end_date": "2025-02-15",
        })

        data = response.json()
        self.assertEqual(data["periods"][0]["period_start"], "2025-01-15")
        self.assertEqual(data["periods"][0]["period_end"], "2025-01-31")
        self.assertEqual(data["periods"][1]["period_start"], "2025-02-01")
        self.assertEqual(data["periods"][1]["period_end"], "2025-02-15")

    # --- Response structure ---

    def test_response_structure(self):
        self._make_tx(-50, self.parent_category, "2025-01-15")

        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
        })

        data = response.json()
        self.assertEqual(data["category_id"], self.parent_category.id)
        self.assertEqual(data["category_name"], "Food")
        self.assertEqual(data["start_date"], "2025-01-01")
        self.assertEqual(data["end_date"], "2025-01-31")
        self.assertIn("periods", data)
        self.assertIn("grand_total_usd", data)
        self.assertIn("malformed_transactions", data)

        period = data["periods"][0]
        self.assertIn("period_start", period)
        self.assertIn("period_end", period)
        self.assertIn("label", period)
        self.assertIn("total_amount_usd", period)
        self.assertIn("children", period)

    def test_multiple_currencies_in_same_period(self):
        self._make_tx(-50, self.parent_category, "2025-01-15")  # USD
        self._make_tx(-600, self.parent_category, "2025-01-20", account=self.ves_account)  # 600 VES / 60 = 10 USD
        self._make_tx(-110, self.parent_category, "2025-01-25", account=self.eur_account)  # 110 EUR / 1.1 = 100 USD

        response = self.client.get(self.url, {
            "category": self.parent_category.id,
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
        })

        data = response.json()
        # 50 + 10 + 100 = 160
        self.assertEqual(data["periods"][0]["total_amount_usd"], 160.0)
        self.assertEqual(data["grand_total_usd"], 160.0)
