import pytz
from faker import Faker
from datetime import datetime, timezone, timedelta
from django.urls import reverse
from django.utils import timezone as django_timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from ..models import Transaction, CurrencyExchange, ExchangeComission, Category
from japb_api.users.models import User
from japb_api.accounts.models import Account
from japb_api.currencies.factories import (
    CurrencyFactory,
    CurrencyConversionHistorialFactory,
)
from japb_api.currencies.models import Currency, CurrencyConversionHistorial


class TestExpensesSummaryViewSet(APITestCase):
    def setUp(self):
        self.fake = Faker(["en-US"])
        self.user = User.objects.create_user(
            email=self.fake.email(),
            username=self.fake.user_name(),
            password=self.fake.password(),
        )
        self.token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token.access_token}")

        # Create currencies
        self.usd_currency = Currency.objects.create(name="USD", default_conversion_source="paralelo")
        self.ves_currency = Currency.objects.create(name="VES", default_conversion_source="paralelo")
        self.eur_currency = Currency.objects.create(name="EUR", default_conversion_source="paralelo")

        # Create accounts
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
        self.eur_account = Account.objects.create(
            name="EUR Account",
            currency=self.eur_currency,
            decimal_places=2,
            user=self.user,
        )

        # Create conversion rates (with date in the past so they work for transactions)
        # Note: date field has auto_now_add=True, so we need to set it after creation
        past_date = django_timezone.now() - timedelta(days=10)
        self.ves_to_usd_conversion = CurrencyConversionHistorial.objects.create(
            currency_from=self.ves_currency,
            currency_to=self.usd_currency,
            rate=60.0,
            source="paralelo",
            user=None,
        )
        self.ves_to_usd_conversion.date = past_date
        self.ves_to_usd_conversion.save()
        
        self.eur_to_usd_conversion = CurrencyConversionHistorial.objects.create(
            currency_from=self.eur_currency,
            currency_to=self.usd_currency,
            rate=1.1,
            source="paralelo",
            user=None,
        )
        self.eur_to_usd_conversion.date = past_date
        self.eur_to_usd_conversion.save()

        # Create categories
        self.parent_category = Category.objects.create(
            name="Food",
            color="#000000",
            description="Food expenses",
            type="expense",
            user=None,  # Global category
        )
        self.child_category = Category.objects.create(
            name="Groceries",
            color="#000000",
            description="Groceries expenses",
            type="expense",
            parent_category=self.parent_category,
            user=None,
        )
        self.other_category = Category.objects.create(
            name="Transportation",
            color="#000000",
            description="Transportation expenses",
            type="expense",
            user=None,
        )

    def test_expenses_summary_7days_default(self):
        """Test expenses summary with default 7 days period"""
        now = django_timezone.now()
        # Create expense transactions in the last 7 days
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-5000,  # -50.00 USD
            description="USD Expense",
            date=now - timedelta(days=3),
            category=self.parent_category,
        )
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-3000,  # -30.00 USD
            description="USD Expense 2",
            date=now - timedelta(days=1),
            category=self.child_category,
        )

        url = reverse("expenses-summary-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["period"], "7d")
        self.assertEqual(len(data["summary"]), 1)
        self.assertEqual(data["summary"][0]["category_name"], "Food")
        self.assertEqual(data["summary"][0]["total_amount_usd"], 80.0)
        self.assertEqual(len(data["summary"][0]["children"]), 1)
        self.assertEqual(data["summary"][0]["children"][0]["category_name"], "Groceries")
        self.assertEqual(data["summary"][0]["children"][0]["total_amount_usd"], 30.0)

    def test_expenses_summary_1month(self):
        """Test expenses summary with 1 month period"""
        now = django_timezone.now()
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-10000,  # -100.00 USD
            description="USD Expense",
            date=now - timedelta(days=15),
            category=self.parent_category,
        )

        url = reverse("expenses-summary-list") + "?period=1m"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["period"], "1m")
        self.assertEqual(len(data["summary"]), 1)
        self.assertEqual(data["summary"][0]["total_amount_usd"], 100.0)

    def test_expenses_summary_excludes_old_transactions(self):
        """Test that transactions older than the period are excluded"""
        now = django_timezone.now()
        # Create transaction within 7 days
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-5000,
            description="Recent Expense",
            date=now - timedelta(days=3),
            category=self.parent_category,
        )
        # Create transaction older than 7 days
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-10000,
            description="Old Expense",
            date=now - timedelta(days=10),
            category=self.parent_category,
        )

        url = reverse("expenses-summary-list") + "?period=7d"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["summary"]), 1)
        self.assertEqual(data["summary"][0]["total_amount_usd"], 50.0)

    def test_expenses_summary_usd_conversion_direct(self):
        """Test USD conversion for USD transactions"""
        now = django_timezone.now()
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-5000,  # -50.00 USD (stored as integer)
            description="USD Expense",
            date=now - timedelta(days=1),
            category=self.parent_category,
        )

        url = reverse("expenses-summary-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["summary"][0]["total_amount_usd"], 50.0)

    def test_expenses_summary_usd_conversion_to_main_currency_amount(self):
        """Test USD conversion using to_main_currency_amount"""
        now = django_timezone.now()
        Transaction.objects.create(
            user=self.user,
            account=self.ves_account,
            amount=-60000,  # -600.00 VES
            to_main_currency_amount=-1000,  # -10.00 USD (stored as integer with 2 decimal places)
            description="VES Expense",
            date=now - timedelta(days=1),
            category=self.parent_category,
        )

        url = reverse("expenses-summary-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["summary"][0]["total_amount_usd"], 10.0)

    def test_expenses_summary_usd_conversion_using_historial(self):
        """Test USD conversion using CurrencyConversionHistorial"""
        now = django_timezone.now()
        Transaction.objects.create(
            user=self.user,
            account=self.ves_account,
            amount=-60000,  # -600.00 VES (no to_main_currency_amount)
            description="VES Expense",
            date=now - timedelta(days=1),
            category=self.parent_category,
        )

        url = reverse("expenses-summary-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # 600.00 VES / 60.0 rate = 10.00 USD
        self.assertEqual(data["summary"][0]["total_amount_usd"], 10.0)

    def test_expenses_summary_malformed_transactions(self):
        """Test that transactions without conversion are added to malformed"""
        now = django_timezone.now()
        # Create currency without conversion rate
        unknown_currency = Currency.objects.create(
            name="UNKNOWN",
            default_conversion_source="paralelo"
        )
        unknown_account = Account.objects.create(
            name="Unknown Account",
            currency=unknown_currency,
            decimal_places=2,
            user=self.user,
        )

        Transaction.objects.create(
            user=self.user,
            account=unknown_account,
            amount=-5000,
            description="Unknown Currency Expense",
            date=now - timedelta(days=1),
            category=self.parent_category,
        )

        url = reverse("expenses-summary-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["summary"]), 0)
        self.assertEqual(len(data["malformed_transactions"]), 1)
        self.assertEqual(data["malformed_transactions"][0]["currency"], "UNKNOWN")
        self.assertEqual(data["malformed_transactions"][0]["reason"], "No conversion rate available")

    def test_expenses_summary_excludes_same_currency_exchanges(self):
        """Test that same-currency exchanges are excluded"""
        now = django_timezone.now()
        # Create same-currency exchange
        exchange = CurrencyExchange.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-5000,
            description="Same Currency Exchange",
            date=now - timedelta(days=1),
            type="from_same_currency",
            category=self.parent_category,
        )
        # Create regular expense
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-3000,
            description="Regular Expense",
            date=now - timedelta(days=1),
            category=self.parent_category,
        )

        url = reverse("expenses-summary-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Should only include regular expense, not the exchange
        self.assertEqual(data["summary"][0]["total_amount_usd"], 30.0)

    def test_expenses_summary_includes_commissions(self):
        """Test that commission transactions are included"""
        now = django_timezone.now()
        # Create exchange transactions for commission
        exchange_from = CurrencyExchange.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-10000,
            description="Exchange From",
            date=now - timedelta(days=1),
            type="from_same_currency",
            category=None,
        )
        exchange_to = CurrencyExchange.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=9500,
            description="Exchange To",
            date=now - timedelta(days=1),
            type="to_same_currency",
            category=None,
        )
        # Create commission
        ExchangeComission.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-500,  # -5.00 USD commission
            description="Commission",
            date=now - timedelta(days=1),
            type="comission",
            exchange_from=exchange_from,
            exchange_to=exchange_to,
            category=self.parent_category,
        )
        # Create regular expense
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-3000,
            description="Regular Expense",
            date=now - timedelta(days=1),
            category=self.parent_category,
        )

        url = reverse("expenses-summary-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Should include both commission and regular expense: 5.0 + 30.0 = 35.0
        self.assertEqual(data["summary"][0]["total_amount_usd"], 35.0)

    def test_expenses_summary_excludes_profits(self):
        """Test that profit transactions are excluded"""
        now = django_timezone.now()
        # Create exchange transactions
        exchange_from = CurrencyExchange.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-10000,
            description="Exchange From",
            date=now - timedelta(days=1),
            type="from_same_currency",
            category=None,
        )
        exchange_to = CurrencyExchange.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=10500,
            description="Exchange To",
            date=now - timedelta(days=1),
            type="to_same_currency",
            category=None,
        )
        # Create profit (should be excluded)
        ExchangeComission.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=500,  # Positive amount (profit)
            description="Profit",
            date=now - timedelta(days=1),
            type="profit",
            exchange_from=exchange_from,
            exchange_to=exchange_to,
            category=self.parent_category,
        )

        url = reverse("expenses-summary-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Profit should be excluded (it's positive amount anyway, but also filtered by type)
        self.assertEqual(len(data["summary"]), 0)

    def test_expenses_summary_category_grouping(self):
        """Test that child categories are grouped under parent categories"""
        now = django_timezone.now()
        # Create transactions with parent category
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-5000,
            description="Parent Category Expense",
            date=now - timedelta(days=1),
            category=self.parent_category,
        )
        # Create transactions with child category
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-3000,
            description="Child Category Expense",
            date=now - timedelta(days=1),
            category=self.child_category,
        )
        # Create transaction with other category
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-2000,
            description="Other Category Expense",
            date=now - timedelta(days=1),
            category=self.other_category,
        )

        url = reverse("expenses-summary-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Should have 2 parent categories: Food (with child) and Transportation
        self.assertEqual(len(data["summary"]), 2)
        # Food category should have total of 50 + 30 = 80
        food_category = next(c for c in data["summary"] if c["category_name"] == "Food")
        self.assertEqual(food_category["total_amount_usd"], 80.0)
        self.assertEqual(len(food_category["children"]), 1)
        self.assertEqual(food_category["children"][0]["total_amount_usd"], 30.0)
        # Transportation should have 20
        transport_category = next(c for c in data["summary"] if c["category_name"] == "Transportation")
        self.assertEqual(transport_category["total_amount_usd"], 20.0)

    def test_expenses_summary_uncategorized_transactions(self):
        """Test that uncategorized transactions are grouped under Uncategorized"""
        now = django_timezone.now()
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-5000,
            description="Uncategorized Expense",
            date=now - timedelta(days=1),
            category=None,
        )

        url = reverse("expenses-summary-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["summary"]), 1)
        self.assertEqual(data["summary"][0]["category_name"], "Uncategorized")
        self.assertEqual(data["summary"][0]["total_amount_usd"], 50.0)

    def test_expenses_summary_sorted_by_amount(self):
        """Test that summary is sorted by total amount descending"""
        now = django_timezone.now()
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-10000,  # 100 USD
            description="Large Expense",
            date=now - timedelta(days=1),
            category=self.other_category,
        )
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-5000,  # 50 USD
            description="Medium Expense",
            date=now - timedelta(days=1),
            category=self.parent_category,
        )
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-2000,  # 20 USD
            description="Small Expense",
            date=now - timedelta(days=1),
            category=self.parent_category,
        )

        url = reverse("expenses-summary-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Should be sorted by amount descending
        self.assertEqual(data["summary"][0]["total_amount_usd"], 100.0)
        self.assertEqual(data["summary"][1]["total_amount_usd"], 70.0)  # 50 + 20

    def test_expenses_summary_unauthorized(self):
        """Test that unauthorized requests are rejected"""
        self.client.credentials(HTTP_AUTHORIZATION=None)
        url = reverse("expenses-summary-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_expenses_summary_only_user_transactions(self):
        """Test that only the authenticated user's transactions are included"""
        now = django_timezone.now()
        # Create another user
        other_user = User.objects.create_user(
            email=self.fake.email(),
            username=self.fake.user_name(),
            password=self.fake.password(),
        )
        # Create transaction for other user
        Transaction.objects.create(
            user=other_user,
            account=self.usd_account,
            amount=-10000,
            description="Other User Expense",
            date=now - timedelta(days=1),
            category=self.parent_category,
        )
        # Create transaction for current user
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-5000,
            description="My Expense",
            date=now - timedelta(days=1),
            category=self.parent_category,
        )

        url = reverse("expenses-summary-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Should only include current user's transaction
        self.assertEqual(data["summary"][0]["total_amount_usd"], 50.0)

    def test_expenses_summary_excludes_income_transactions(self):
        """Test that income transactions (positive amounts) are excluded"""
        now = django_timezone.now()
        # Create income transaction
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=5000,  # Positive amount (income)
            description="Income",
            date=now - timedelta(days=1),
            category=None,
        )
        # Create expense transaction
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-3000,  # Negative amount (expense)
            description="Expense",
            date=now - timedelta(days=1),
            category=self.parent_category,
        )

        url = reverse("expenses-summary-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Should only include expense
        self.assertEqual(data["summary"][0]["total_amount_usd"], 30.0)

    def test_expenses_summary_multiple_currencies(self):
        """Test expenses summary with multiple currencies"""
        now = django_timezone.now()
        # USD transaction
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-5000,  # -50.00 USD
            description="USD Expense",
            date=now - timedelta(days=1),
            category=self.parent_category,
        )
        # VES transaction with conversion
        Transaction.objects.create(
            user=self.user,
            account=self.ves_account,
            amount=-60000,  # -600.00 VES = -10.00 USD (rate 60)
            description="VES Expense",
            date=now - timedelta(days=1),
            category=self.parent_category,
        )
        # EUR transaction with conversion
        Transaction.objects.create(
            user=self.user,
            account=self.eur_account,
            amount=-11000,  # -110.00 EUR = -100.00 USD (rate 1.1)
            description="EUR Expense",
            date=now - timedelta(days=1),
            category=self.parent_category,
        )

        url = reverse("expenses-summary-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Total: 50 + 10 + 100 = 160 USD
        self.assertEqual(data["summary"][0]["total_amount_usd"], 160.0)

    def test_expenses_summary_current_week(self):
        """Test expenses summary with current week period"""
        now = django_timezone.now()
        # Calculate start of current week (Monday)
        days_since_monday = now.weekday()  # Monday is 0, Sunday is 6
        week_start = now - timedelta(days=days_since_monday)
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Create transaction within current week
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-5000,  # -50.00 USD
            description="Current Week Expense",
            date=week_start + timedelta(days=1),
            category=self.parent_category,
        )
        # Create transaction before current week (should be excluded)
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-10000,  # -100.00 USD
            description="Previous Week Expense",
            date=week_start - timedelta(days=1),
            category=self.parent_category,
        )

        url = reverse("expenses-summary-list") + "?period=current_week"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["period"], "current_week")
        # Should only include transaction from current week
        self.assertEqual(len(data["summary"]), 1)
        self.assertEqual(data["summary"][0]["total_amount_usd"], 50.0)

    def test_expenses_summary_current_month(self):
        """Test expenses summary with current month period"""
        now = django_timezone.now()
        # Calculate start of current month
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Create transaction within current month
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-5000,  # -50.00 USD
            description="Current Month Expense",
            date=month_start + timedelta(days=5),
            category=self.parent_category,
        )
        # Create transaction before current month (should be excluded)
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-10000,  # -100.00 USD
            description="Previous Month Expense",
            date=month_start - timedelta(days=1),
            category=self.parent_category,
        )

        url = reverse("expenses-summary-list") + "?period=current_month"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["period"], "current_month")
        # Should only include transaction from current month
        self.assertEqual(len(data["summary"]), 1)
        self.assertEqual(data["summary"][0]["total_amount_usd"], 50.0)

