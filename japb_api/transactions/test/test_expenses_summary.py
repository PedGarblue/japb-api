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

    def test_expenses_summary_excludes_all_currency_exchanges(self):
        """Test that all currency exchanges (same-currency and different-currency) are excluded"""
        now = django_timezone.now()
        # Create same-currency exchange
        same_currency_exchange = CurrencyExchange.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-5000,
            description="Same Currency Exchange",
            date=now - timedelta(days=1),
            type="from_same_currency",
            category=self.parent_category,
        )
        # Create different-currency exchange
        different_currency_exchange = CurrencyExchange.objects.create(
            user=self.user,
            account=self.ves_account,
            amount=-60000,
            description="Different Currency Exchange",
            date=now - timedelta(days=1),
            type="from_different_currency",
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
        # Should only include regular expense, not any exchanges
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
        test_now = django_timezone.now()
        days_since_monday = test_now.weekday()
        current_week_monday = test_now - timedelta(days=days_since_monday)
        current_week_monday = current_week_monday.replace(hour=0, minute=0, second=0, microsecond=0)
        
        if days_since_monday == 0:
            transaction_date = test_now - timedelta(minutes=10)
            if transaction_date < current_week_monday:
                transaction_date = current_week_monday + timedelta(minutes=5)
                if transaction_date >= test_now:
                    transaction_date = test_now - timedelta(minutes=1)
                    if transaction_date < current_week_monday:
                        transaction_date = current_week_monday + timedelta(seconds=1)
        elif days_since_monday == 6:
            transaction_date = current_week_monday + timedelta(days=2, hours=12)
        else:
            transaction_date = test_now - timedelta(days=1)
            if transaction_date < current_week_monday:
                transaction_date = current_week_monday + timedelta(days=1, hours=12)
        
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-5000,
            description="Current Week Expense",
            date=transaction_date,
            category=self.parent_category,
        )
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-10000,
            description="Previous Week Expense",
            date=current_week_monday - timedelta(days=1),
            category=self.parent_category,
        )

        url = reverse("expenses-summary-list") + "?period=current_week"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["period"], "current_week")
        
        self.assertEqual(len(data["summary"]), 1, 
                        f"Expected 1 summary item, got {len(data['summary'])}. "
                        f"Transaction date: {transaction_date}, "
                        f"API from_date: {data.get('from_date')}, "
                        f"API to_date: {data.get('to_date')}, "
                        f"Current week Monday: {current_week_monday}, "
                        f"Days since Monday: {days_since_monday}")
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

    def test_expenses_summary_total_field_single_category(self):
        """Test that total field is present and correct for single category"""
        now = django_timezone.now()
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-5000,  # -50.00 USD
            description="USD Expense",
            date=now - timedelta(days=1),
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
        # Total should be sum of all category totals: 50 + 30 = 80
        self.assertIn("total", data)
        self.assertEqual(data["total"], 80.0)
        self.assertEqual(data["summary"][0]["total_amount_usd"], 80.0)

    def test_expenses_summary_total_field_multiple_categories(self):
        """Test that total field correctly sums multiple categories"""
        now = django_timezone.now()
        # Create transactions in different categories
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-10000,  # -100.00 USD
            description="Food Expense",
            date=now - timedelta(days=1),
            category=self.parent_category,
        )
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-5000,  # -50.00 USD
            description="Transportation Expense",
            date=now - timedelta(days=1),
            category=self.other_category,
        )
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-2000,  # -20.00 USD
            description="Uncategorized Expense",
            date=now - timedelta(days=1),
            category=None,
        )

        url = reverse("expenses-summary-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Total should be sum of all categories: 100 + 50 + 20 = 170
        self.assertIn("total", data)
        self.assertEqual(data["total"], 170.0)
        # Verify individual category totals
        category_totals = [cat["total_amount_usd"] for cat in data["summary"]]
        self.assertEqual(sum(category_totals), 170.0)

    def test_expenses_summary_total_field_with_commissions(self):
        """Test that total field includes commissions"""
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
            amount=-3000,  # -30.00 USD
            description="Regular Expense",
            date=now - timedelta(days=1),
            category=self.parent_category,
        )

        url = reverse("expenses-summary-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Total should include both commission and regular expense: 5 + 30 = 35
        self.assertIn("total", data)
        self.assertEqual(data["total"], 35.0)

    def test_expenses_summary_total_field_excludes_profits(self):
        """Test that total field excludes profits"""
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
        # Create regular expense
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-2000,  # -20.00 USD
            description="Regular Expense",
            date=now - timedelta(days=1),
            category=self.parent_category,
        )

        url = reverse("expenses-summary-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Total should only include regular expense, not profit: 20
        self.assertIn("total", data)
        self.assertEqual(data["total"], 20.0)

    def test_expenses_summary_total_field_multiple_currencies(self):
        """Test that total field correctly sums expenses in multiple currencies"""
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
        self.assertIn("total", data)
        self.assertEqual(data["total"], 160.0)

    def test_expenses_summary_total_field_different_periods(self):
        """Test that total field works correctly with different periods"""
        now = django_timezone.now()
        # Create transactions in different time periods
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-5000,  # -50.00 USD (within 7 days)
            description="Recent Expense",
            date=now - timedelta(days=3),
            category=self.parent_category,
        )
        Transaction.objects.create(
            user=self.user,
            account=self.usd_account,
            amount=-10000,  # -100.00 USD (within 30 days but not 7)
            description="Older Expense",
            date=now - timedelta(days=15),
            category=self.parent_category,
        )

        # Test 7d period
        url = reverse("expenses-summary-list") + "?period=7d"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("total", data)
        self.assertEqual(data["total"], 50.0)

        # Test 1m period
        url = reverse("expenses-summary-list") + "?period=1m"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("total", data)
        self.assertEqual(data["total"], 150.0)  # 50 + 100

    def test_expenses_summary_total_field_empty_summary(self):
        """Test that total field is 0 when there are no expenses"""
        url = reverse("expenses-summary-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("total", data)
        self.assertEqual(data["total"], 0.0)
        self.assertEqual(len(data["summary"]), 0)

