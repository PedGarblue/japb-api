from datetime import datetime, timedelta

import pytz
from django.urls import reverse
from django.utils import timezone as django_timezone
from faker import Faker
from freezegun import freeze_time
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from ..models import Category, CurrencyExchange, ExchangeComission, Transaction
from japb_api.accounts.models import Account
from japb_api.currencies.models import Currency, CurrencyConversionHistorial
from japb_api.users.models import User


def _transaction_date_safe_for_current_month(now):
    """Avoid dates before month start when ``now`` is on the 1st (e.g. yesterday was last month)."""
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return max(month_start, now - timedelta(days=1))


class TestCashflowSummaryViewSet(APITestCase):
    def setUp(self):
        self.fake = Faker(["en-US"])
        self.user = User.objects.create_user(
            email=self.fake.email(),
            username=self.fake.user_name(),
            password=self.fake.password(),
        )
        self.token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token.access_token}")
        # Keep auth stable in tests that use freeze_time and jump across dates.
        self.client.force_authenticate(user=self.user)

        self.usd_currency = Currency.objects.create(
            name="USD", default_conversion_source="paralelo"
        )
        self.ves_currency = Currency.objects.create(
            name="VES", default_conversion_source="paralelo"
        )

        self.usd_account = Account.objects.create(
            name="USD Account",
            currency=self.usd_currency,
            decimal_places=2,
            user=self.user,
        )
        self.ves_account = Account.objects.create(
            name="VES Account",
            currency=self.ves_currency,
            decimal_places=2,
            user=self.user,
        )

        past_date = django_timezone.now() - timedelta(days=10)
        self.ves_to_usd = CurrencyConversionHistorial.objects.create(
            currency_from=self.ves_currency,
            currency_to=self.usd_currency,
            rate=60.0,
            source="paralelo",
            user=None,
        )
        self.ves_to_usd.date = past_date
        self.ves_to_usd.save()

        self.expense_category = Category.objects.create(
            name="Food",
            color="#000000",
            description="Food",
            type="expense",
            user=None,
        )
        self.income_category = Category.objects.create(
            name="Salary",
            color="#000000",
            description="Salary",
            type="income",
            user=None,
        )

    def test_invalid_period_returns_400(self):
        url = reverse("cashflow-summary-list")
        response = self.client.get(url, {"period": "7d"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("period", response.json()["error"])

    def test_default_period_is_current_month(self):
        frozen = django_timezone.make_aware(
            datetime(2026, 4, 15, 12, 0, 0),
            timezone=pytz.UTC,
        )
        with freeze_time(frozen):
            url = reverse("cashflow-summary-list")
            response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["period"], "current_month")
        self.assertTrue(data["from_date"].startswith("2026-04-01"))

    def test_fcf_income_minus_expenses(self):
        now = django_timezone.now()
        tx_date = _transaction_date_safe_for_current_month(now)
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=10_000,
            description="Income",
            date=tx_date,
            category=self.income_category,
        )
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-3_000,
            description="Expense",
            date=tx_date,
            category=self.expense_category,
        )

        url = reverse("cashflow-summary-list")
        response = self.client.get(url, {"period": "current_month"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["income_total_usd"], 100.0)
        self.assertEqual(data["expense_total_usd"], 30.0)
        self.assertEqual(data["free_cash_flow_usd"], 70.0)

    def test_excludes_currency_exchanges(self):
        now = django_timezone.now()
        tx_date = _transaction_date_safe_for_current_month(now)
        CurrencyExchange.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-5_000,
            description="Exchange",
            date=tx_date,
            type="from_same_currency",
            category=self.expense_category,
        )
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-2_000,
            description="Expense",
            date=tx_date,
            category=self.expense_category,
        )

        url = reverse("cashflow-summary-list")
        response = self.client.get(url, {"period": "current_month"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["expense_total_usd"], 20.0)
        self.assertEqual(data["income_total_usd"], 0.0)

    def test_excludes_exchange_profit(self):
        now = django_timezone.now()
        tx_date = _transaction_date_safe_for_current_month(now)
        exchange_from = CurrencyExchange.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-10_000,
            description="From",
            date=tx_date,
            type="from_same_currency",
            category=None,
        )
        exchange_to = CurrencyExchange.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=9_500,
            description="To",
            date=tx_date,
            type="to_same_currency",
            category=None,
        )
        ExchangeComission.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=500,
            description="Profit",
            date=tx_date,
            type="profit",
            exchange_from=exchange_from,
            exchange_to=exchange_to,
            category=None,
        )
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=8_000,
            description="Salary",
            date=tx_date,
            category=self.income_category,
        )

        url = reverse("cashflow-summary-list")
        response = self.client.get(url, {"period": "current_month"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["income_total_usd"], 80.0)

    def test_this_quarter_only_includes_transactions_in_quarter(self):
        frozen = django_timezone.make_aware(
            datetime(2026, 6, 15, 12, 0, 0),
            timezone=pytz.UTC,
        )
        in_quarter = frozen - timedelta(days=5)
        before_quarter = django_timezone.make_aware(
            datetime(2026, 3, 31, 12, 0, 0),
            timezone=pytz.UTC,
        )

        with freeze_time(frozen):
            Transaction.objects.create(
                user=self.user,
                account=self.usd_account,
                amount=-1_000,
                description="In Q2",
                date=in_quarter,
                category=self.expense_category,
            )
            Transaction.objects.create(
                user=self.user,
                account=self.usd_account,
                amount=-9_000,
                description="Before Q2",
                date=before_quarter,
                category=self.expense_category,
            )
            url = reverse("cashflow-summary-list")
            response = self.client.get(url, {"period": "this_quarter"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["period"], "this_quarter")
        self.assertTrue(data["from_date"].startswith("2026-04-01"))
        self.assertEqual(data["expense_total_usd"], 10.0)

    def test_this_year_excludes_prior_year(self):
        frozen = django_timezone.make_aware(
            datetime(2026, 6, 1, 12, 0, 0),
            timezone=pytz.UTC,
        )
        with freeze_time(frozen):
            Transaction.objects.create(
                user=self.user,
                account=self.usd_account,
                amount=-5_000,
                description="This year",
                date=frozen - timedelta(days=1),
                category=self.expense_category,
            )
            Transaction.objects.create(
                user=self.user,
                account=self.usd_account,
                amount=-20_000,
                description="Last year",
                date=django_timezone.make_aware(
                    datetime(2025, 12, 15, 12, 0, 0),
                    timezone=pytz.UTC,
                ),
                category=self.expense_category,
            )
            url = reverse("cashflow-summary-list")
            response = self.client.get(url, {"period": "this_year"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["period"], "this_year")
        self.assertTrue(data["from_date"].startswith("2026-01-01"))
        self.assertEqual(data["expense_total_usd"], 50.0)

    def test_malformed_when_no_conversion(self):
        unknown_currency = Currency.objects.create(
            name="UNKNOWN", default_conversion_source="paralelo"
        )
        unknown_account = Account.objects.create(
            name="Unknown",
            currency=unknown_currency,
            decimal_places=2,
            user=self.user,
        )
        now = django_timezone.now()
        tx_date = _transaction_date_safe_for_current_month(now)
        Transaction.objects.create(
            user=self.user,
            account=unknown_account,
            amount=-5_000,
            description="No rate",
            date=tx_date,
            category=self.expense_category,
        )

        url = reverse("cashflow-summary-list")
        response = self.client.get(url, {"period": "current_month"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["expense_total_usd"], 0.0)
        self.assertEqual(len(data["malformed_transactions"]), 1)
        self.assertEqual(
            data["malformed_transactions"][0]["reason"],
            "No conversion rate available",
        )
