import pytz
from faker import Faker
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from ..models import Currency
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
        self.assertEqual(Currency.objects.count(), 1)
        self.assertEqual(Currency.objects.get().name, "USD")
        self.assertEqual(Currency.objects.get().symbol, "$")

    def test_api_user_cannot_create_currency(self):
        self.response = self.client.post(
            reverse("currencies-list"), self.data, format="json"
        )
        self.assertEqual(self.response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Currency.objects.count(), 0)

    def test_api_get_currency_list(self):
        currency = CurrencyFactory()
        url = reverse("currencies-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Currency.objects.count(), 1)
        self.assertEqual(response.json()["results"][0]["name"], currency.name)
        self.assertEqual(response.json()["results"][0]["symbol"], currency.symbol)

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
        foreign_currency = Currency.objects.create(name="EUR", symbol="€")

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
        self.assertEqual(response.json()["results"][1]["id"], main_currency.id)
        self.assertEqual(response.json()["results"][1]["name"], "USD")
        self.assertEqual(response.json()["results"][1]["symbol"], "$")
        self.assertEqual(
            response.json()["results"][1]["balance"],
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
        self.assertEqual(Currency.objects.count(), 1)

    def test_api_get_a_currency_with_balance(self):
        MAIN_ACCOUNT_TRANSACTIONS_AMOUNTS = [100, 200]
        SECONDARY_ACCOUNT_TRANSACTIONS_AMOUNTS = [200, -100]
        MAIN_CURRENCY_DECIMAL_PLACES_MULTIPLIER = 100
        SUM_OF_MAIN_CURRENCY_TRANSACTIONS = (
            400 / MAIN_CURRENCY_DECIMAL_PLACES_MULTIPLIER
        )

        main_currency = Currency.objects.create(name="USD", symbol="$")
        foreign_currency = Currency.objects.create(name="EUR", symbol="€")

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
        self.assertEqual(Currency.objects.get().name, "Super USD")
        self.assertEqual(Currency.objects.get().symbol, "$$")

    def test_api_admin_can_delete_a_currency(self):
        currency = Currency.objects.create(name="USD", symbol="$")
        admin = UserFactory(is_staff=True)
        admin_token = RefreshToken.for_user(admin)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_token.access_token}")
        response = self.client.delete(
            reverse("currencies-detail", kwargs={"pk": currency.id}), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Currency.objects.count(), 0)
