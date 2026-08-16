import pytz
from faker import Faker
from datetime import datetime, timezone, timedelta
from django.urls import reverse
from django.utils import timezone as django_timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from ..models import (
    Transaction,
    TransactionGroup,
    CurrencyExchange,
    ExchangeComission,
    Category,
    TransactionItem,
)
from ..factories import TransactionFactory, CategoryFactory, ExchangeComissionFactory, CurrencyExchangeFactory
from japb_api.users.models import User
from japb_api.accounts.models import Account
from japb_api.currencies.factories import (
    CurrencyFactory,
    CurrencyConversionHistorialFactory,
)
from japb_api.currencies.models import Currency
from japb_api.products.models import Product


class TestCurrencyTransaction(APITestCase):
    def setUp(self):
        self.fake = Faker(["en-US"])
        self.user = User.objects.create_user(
            email=self.fake.email(),
            username=self.fake.user_name(),
            password=self.fake.password(),
        )
        self.token = RefreshToken.for_user(self.user)

        self.currency = Currency.objects.create(name="VES", default_conversion_source="paralelo")
        self.account = Account.objects.create(
            name="Test Account", currency=self.currency, decimal_places=2
        )
        self.category = Category.objects.create(
            name="Food", color="#000000", description="Food expenses"
        )

        self.main_currency = CurrencyFactory(name="USD")

        self.current_conversion = CurrencyConversionHistorialFactory(
            currency_from=self.currency,
            currency_to=self.main_currency,
            date=datetime.now(tz=timezone.utc),
            rate=60,
            source="paralelo",
        )

        self.data = {
            "amount": -50,
            "description": "Purchase",
            "account": self.account.id,
            "date": datetime.now(tz=timezone.utc),
            "category": self.category.id,
        }
        self.data2 = {
            "amount": -30,
            "description": "Purchase2",
            "account": self.account.id,
            "date": datetime.now(tz=timezone.utc),
            "category": self.category.id,
        }
        self.data3 = {
            "amount": -500,
            "description": "Purchase3",
            "account": self.account.id,
            "date": datetime.now(tz=timezone.utc),
            "category": self.category.id,
        }
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token.access_token}")

        self.response = self.client.post(
            reverse("transactions-list"), self.data, format="json"
        )

        # Create a product for testing transaction items
        self.product = Product.objects.create(
            name="Test Product",
        )

    def test_api_create_transaction(self):
        self.assertEqual(self.response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Transaction.objects.count(), 1)
        transaction = Transaction.objects.get()
        self.assertEqual(transaction.description, "Purchase")
        self.assertEqual(transaction.category, self.category)
        self.assertEqual(transaction.amount, -5000)
        self.assertEqual(transaction.user, self.user)
        # Test transaction with current date uses current conversion
        self.assertEqual(
            transaction.to_main_currency_amount,
            round(-5000 / self.current_conversion.rate),
        )

    def test_api_create_transaction_unauthorized(self):
        self.client.credentials(HTTP_AUTHORIZATION=None)
        response = self.client.post(
            reverse("transactions-list"), self.data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_api_create_transaction_handles_decimal_places(self):
        Transaction.objects.all().delete()
        # create an account with 3 decimal places
        account = Account.objects.create(
            name="Binance BTC", currency=self.currency, decimal_places=8
        )
        data = {
            "amount": 0.00040000,
            "description": "Purchase",
            "account": account.id,
            "date": datetime.now(tz=timezone.utc),
        }
        response = self.client.post(reverse("transactions-list"), data, format="json")
        transaction = Transaction.objects.get()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Transaction.objects.count(), 1)
        # the amount should be saved as integer when the account decimal place are greater than 2
        # in the account serializer, the amount is divided by 10 ** account.decimal_places
        self.assertEqual(transaction.amount, 40000)

    def test_api_create_multiple_transactions(self):
        data = [self.data, self.data2, self.data3]
        self.client.post(reverse("transactions-list"), data, format="json")

        self.assertEqual(self.response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.response.json()[0]["amount"], "-50.00")
        # 3 + the one created at setUp()
        self.assertEqual(Transaction.objects.count(), 4)

    def test_api_create_transaction_with_transaction_items(self):
        Transaction.objects.all().delete()
        TransactionItem.objects.all().delete()

        data = {
            "amount": -50,
            "description": "Purchase",
            "account": self.account.id,
            "date": datetime.now(tz=timezone.utc),
            "category": self.category.id,
            "transaction_items": [
                {
                    "product": self.product.id,
                    "quantity": 1,
                }
            ],
        }

        response = self.client.post(reverse("transactions-list"), data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertEqual(TransactionItem.objects.count(), 1)

    def test_api_get_user_transactions(self):
        # non user transaction
        TransactionFactory()
        url = reverse("transactions-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # only one transaction created by the user
        self.assertEqual(len(response.json()["results"]), 1)
        # amount
        self.assertEquals(response.json()["results"][0]["amount"], "-50.00")
        self.assertEquals(response.json()["results"][0]["category"], self.category.id)

    def test_api_get_a_user_transaction(self):
        transaction = Transaction.objects.get()
        response = self.client.get(
            reverse("transactions-detail", kwargs={"pk": transaction.id}), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["amount"], "-50.00")
        self.assertEquals(response.json()["category"], self.category.id)
        self.assertEqual(Transaction.objects.count(), 1)

    def test_api_get_a_transaction_not_found(self):
        Transaction.objects.get()
        response = self.client.get(
            reverse("transactions-detail", kwargs={"pk": 3}), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_api_can_update_a_transaction(self):
        transaction = Transaction.objects.get()
        new_data = {
            "description": "New transaction",
            "amount": -5,
            "account": self.account.id,
            "date": datetime.now(tz=timezone.utc),
        }
        response = self.client.put(
            reverse("transactions-detail", kwargs={"pk": transaction.id}),
            data=new_data,
            format="json",
        )
        updated_transaction = Transaction.objects.get()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(updated_transaction.description, "New transaction")
        self.assertEqual(updated_transaction.amount, -500)

    def test_api_update_transaction_updates_to_main_currency_amount(self):
        transaction = Transaction.objects.get()
        new_data = {
            "description": "New transaction",
            "amount": -1200,
            "account": self.account.id,
            "date": transaction.date,
        }

        response = self.client.put(
            reverse("transactions-detail", kwargs={"pk": transaction.id}),
            data=new_data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        transaction.refresh_from_db()
        self.assertEqual(transaction.to_main_currency_amount, -2000)

    def test_api_update_transaction_removes_to_main_currency_amount_when_currency_changes(self):
        transaction = Transaction.objects.get()

        # create a new account with a different currency
        account2 = Account.objects.create(
            name="Test Account 2", currency=self.main_currency, decimal_places=2
        )

        new_data = {
            "description": "New transaction",
            "amount": -5,
            "account": account2.id,
            "date": datetime.now(tz=timezone.utc),
        }

        self.assertEqual(transaction.to_main_currency_amount, -83)

        response = self.client.put(
            reverse("transactions-detail", kwargs={"pk": transaction.id}),
            data=new_data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        transaction.refresh_from_db()

        self.assertEqual(transaction.to_main_currency_amount, None)

    def test_api_update_transaction_unauthorized(self):
        transaction = Transaction.objects.get()
        new_data = {
            "description": "New transaction",
            "amount": -5,
            "account": self.account.id,
            "date": datetime.now(tz=timezone.utc),
        }
        self.client.credentials(HTTP_AUTHORIZATION=None)
        response = self.client.put(
            reverse("transactions-detail", kwargs={"pk": transaction.id}),
            data=new_data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_api_cannot_update_non_same_user_transaction(self):
        transaction = Transaction.objects.get()
        user = User.objects.create_user(
            email=self.fake.email(),
            username=self.fake.user_name(),
            password=self.fake.password(),
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}"
        )
        new_data = {
            "description": "New transaction",
            "amount": -5,
            "account": self.account.id,
            "date": datetime.now(tz=timezone.utc),
        }
        response = self.client.put(
            reverse("transactions-detail", kwargs={"pk": transaction.id}),
            data=new_data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_api_can_delete_a_transaction(self):
        transaction = Transaction.objects.get()
        response = self.client.delete(
            reverse("transactions-detail", kwargs={"pk": transaction.id}), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_api_delete_transaction_unauthorized(self):
        transaction = Transaction.objects.get()
        self.client.credentials(HTTP_AUTHORIZATION=None)
        response = self.client.delete(
            reverse("transactions-detail", kwargs={"pk": transaction.id}), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_api_get_transaction_by_custom_date(self):
        # add transacions to the account
        account = self.account
        transactions = [
            Transaction(
                amount=10,
                description="transaction 1",
                account=account,
                date=datetime(2023, 1, 1, tzinfo=pytz.UTC),
                user=self.user,
            ),
            Transaction(
                amount=30,
                description="transaction 2",
                account=account,
                date=datetime(2023, 3, 1, tzinfo=pytz.UTC),
                user=self.user,
            ),
            Transaction(
                amount=25,
                description="transaction 3",
                account=account,
                date=datetime(2023, 3, 1, tzinfo=pytz.UTC),
                user=self.user,
            ),
        ]
        Transaction.objects.bulk_create(transactions)

        url = (
            reverse("transactions-list") + "?start_date=2023-02-01&end_date=2023-03-10"
        )
        response = self.client.get(url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Transaction.objects.count(), 4)
        self.assertEqual(len(response.json()["results"]), 2)
        self.assertEqual(response.json()["results"][1]["description"], "transaction 2")
        self.assertEqual(response.json()["results"][0]["description"], "transaction 3")

    def test_api_get_transaction_by_datetime(self):
        # add transacions to the account
        account = self.account
        transactions = [
            Transaction(
                amount=10,
                description="transaction 1",
                account=account,
                date=datetime(2023, 1, 1, tzinfo=pytz.UTC),
                user=self.user,
            ),
            Transaction(
                amount=30,
                description="transaction 2",
                account=account,
                date=datetime(2023, 3, 1, tzinfo=pytz.UTC),
                user=self.user,
            ),
            Transaction(
                amount=25,
                description="transaction 3",
                account=account,
                date=datetime(2023, 3, 1, tzinfo=pytz.UTC),
                user=self.user,
            ),
        ]
        Transaction.objects.bulk_create(transactions)

        url = (
            reverse("transactions-list") + "?start_date=2023-03-01T00:00:00Z&end_date=2023-03-01T23:59:59Z"
        )
        response = self.client.get(url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Transaction.objects.count(), 4)
        self.assertEqual(len(response.json()["results"]), 2)
        self.assertEqual(response.json()["results"][1]["description"], "transaction 2")
        self.assertEqual(response.json()["results"][0]["description"], "transaction 3")

    def test_api_get_transaction_by_account(self):
        # add transacions to the account
        account = self.account
        account2 = Account.objects.create(name="Test Account 2", currency=self.currency)
        transactions = [
            Transaction(
                amount=10,
                description="transaction 1",
                account=account,
                date=datetime(2023, 1, 1, tzinfo=pytz.UTC),
                user=self.user,
            ),
            Transaction(
                amount=30,
                description="transaction 2",
                account=account,
                date=datetime(2023, 3, 1, tzinfo=pytz.UTC),
                user=self.user,
            ),
            Transaction(
                amount=25,
                description="transaction 3",
                account=account2,
                date=datetime(2023, 3, 1, tzinfo=pytz.UTC),
                user=self.user,
            ),
        ]
        Transaction.objects.bulk_create(transactions)

        url = reverse("transactions-list") + "?account=" + str(account.id)
        response = self.client.get(url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()["results"]), 3)
        self.assertEqual(response.json()["results"][0]["description"], "Purchase")
        self.assertEqual(response.json()["results"][1]["description"], "transaction 2")
        self.assertEqual(response.json()["results"][2]["description"], "transaction 1")

    def test_api_get_transaction_by_currency(self):
        # add transacions to the account
        selectedCurrency = Currency.objects.create(name="USD")
        selectedAccount = Account.objects.create(
            name="Test Account 2", currency=selectedCurrency
        )
        nonSelectedCurrency = Currency.objects.create(name="EUR")
        account2 = Account.objects.create(
            name="Test Account 2", currency=nonSelectedCurrency
        )
        transactions = [
            Transaction(
                amount=10,
                description="transaction 1",
                account=selectedAccount,
                date=datetime(2023, 1, 1, tzinfo=pytz.UTC),
                user=self.user,
            ),
            Transaction(
                amount=30,
                description="transaction 2",
                account=selectedAccount,
                date=datetime(2023, 3, 1, tzinfo=pytz.UTC),
                user=self.user,
            ),
            Transaction(
                amount=40,
                description="transaction 3",
                account=selectedAccount,
                date=datetime(2023, 3, 1, tzinfo=pytz.UTC),
                user=self.user,
            ),
            Transaction(
                amount=25,
                description="transaction 4",
                account=account2,
                date=datetime(2023, 3, 1, tzinfo=pytz.UTC),
                user=self.user,
            ),
        ]
        Transaction.objects.bulk_create(transactions)

        url = reverse("transactions-list") + "?currency=" + str(selectedCurrency.id)
        response = self.client.get(url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()["results"]), 3)
        self.assertEqual(response.json()["results"][0]["description"], "transaction 3")
        self.assertEqual(response.json()["results"][1]["description"], "transaction 2")
        self.assertEqual(response.json()["results"][2]["description"], "transaction 1")

    def test_api_get_transaction_by_category(self):
        # add transactions with different categories
        account = self.account
        parent_category = Category.objects.create(
            name="Food", color="#000000", description="Food expenses", user=self.user
        )
        child_category = Category.objects.create(
            name="Groceries",
            color="#000000",
            description="Groceries expenses",
            parent_category=parent_category,
            user=self.user,
        )
        other_category = Category.objects.create(
            name="Transport", color="#000000", description="Transport expenses", user=self.user
        )
        transactions = [
            Transaction(
                amount=10,
                description="transaction 1 - parent category",
                account=account,
                date=datetime(2023, 1, 1, tzinfo=pytz.UTC),
                category=parent_category,
                user=self.user,
            ),
            Transaction(
                amount=30,
                description="transaction 2 - child category",
                account=account,
                date=datetime(2023, 3, 1, tzinfo=pytz.UTC),
                category=child_category,
                user=self.user,
            ),
            Transaction(
                amount=40,
                description="transaction 3 - other category",
                account=account,
                date=datetime(2023, 3, 1, tzinfo=pytz.UTC),
                category=other_category,
                user=self.user,
            ),
            Transaction(
                amount=25,
                description="transaction 4 - no category",
                account=account,
                date=datetime(2023, 3, 1, tzinfo=pytz.UTC),
                category=None,
                user=self.user,
            ),
        ]
        Transaction.objects.bulk_create(transactions)

        # Test default behavior: filtering by parent category includes children
        url = reverse("transactions-list") + "?category=" + str(parent_category.id)
        response = self.client.get(url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()["results"]), 2)
        self.assertEqual(response.json()["results"][0]["description"], "transaction 2 - child category")
        self.assertEqual(response.json()["results"][1]["description"], "transaction 1 - parent category")
        # Verify all returned transactions have the parent or child category
        category_ids = [parent_category.id, child_category.id]
        for result in response.json()["results"]:
            self.assertIn(result["category"], category_ids)

    def test_api_get_transaction_by_category_exclude_children(self):
        # Test exclude_children flag: filtering by parent category excludes children
        account = self.account
        parent_category = Category.objects.create(
            name="Food", color="#000000", description="Food expenses", user=self.user
        )
        child_category = Category.objects.create(
            name="Groceries",
            color="#000000",
            description="Groceries expenses",
            parent_category=parent_category,
            user=self.user,
        )
        transactions = [
            Transaction(
                amount=10,
                description="transaction 1 - parent category",
                account=account,
                date=datetime(2023, 1, 1, tzinfo=pytz.UTC),
                category=parent_category,
                user=self.user,
            ),
            Transaction(
                amount=30,
                description="transaction 2 - child category",
                account=account,
                date=datetime(2023, 3, 1, tzinfo=pytz.UTC),
                category=child_category,
                user=self.user,
            ),
        ]
        Transaction.objects.bulk_create(transactions)

        # Test with exclude_children=true: should only return parent category transactions
        url = (
            reverse("transactions-list")
            + "?category="
            + str(parent_category.id)
            + "&exclude_children=true"
        )
        response = self.client.get(url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()["results"]), 1)
        self.assertEqual(response.json()["results"][0]["description"], "transaction 1 - parent category")
        self.assertEqual(response.json()["results"][0]["category"], parent_category.id)

    def test_api_get_transaction_by_child_category(self):
        # Test filtering by child category (should work normally, no children to include)
        account = self.account
        parent_category = Category.objects.create(
            name="Food", color="#000000", description="Food expenses", user=self.user
        )
        child_category = Category.objects.create(
            name="Groceries",
            color="#000000",
            description="Groceries expenses",
            parent_category=parent_category,
            user=self.user,
        )
        transactions = [
            Transaction(
                amount=10,
                description="transaction 1 - parent category",
                account=account,
                date=datetime(2023, 1, 1, tzinfo=pytz.UTC),
                category=parent_category,
                user=self.user,
            ),
            Transaction(
                amount=30,
                description="transaction 2 - child category",
                account=account,
                date=datetime(2023, 3, 1, tzinfo=pytz.UTC),
                category=child_category,
                user=self.user,
            ),
        ]
        Transaction.objects.bulk_create(transactions)

        # Test filtering by child category: should only return that child category
        url = reverse("transactions-list") + "?category=" + str(child_category.id)
        response = self.client.get(url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()["results"]), 1)
        self.assertEqual(response.json()["results"][0]["description"], "transaction 2 - child category")
        self.assertEqual(response.json()["results"][0]["category"], child_category.id)

    def test_api_get_transaction_by_exclude_same_currency_exchanges(self):
        # add transacions to the account
        account = self.account
        account2 = Account.objects.create(name="Test Account 2", currency=self.currency)
        ex1 = CurrencyExchange.objects.create(
            amount=-50,
            description="Exchange USD to USD",
            account=account,
            date=datetime(2023, 1, 1, tzinfo=pytz.UTC),
            type="from_same_currency",
            user=self.user,
        )
        ex2 = CurrencyExchange.objects.create(
            amount=50,
            description="Exchange USD to USD",
            account=account2,
            date=datetime(2023, 1, 1, tzinfo=pytz.UTC),
            type="to_same_currency",
            related_transaction=ex1,
            user=self.user,
        )
        ex1.related_transaction = ex2
        ex1.save()

        transactions = [
            Transaction(
                amount=10,
                description="transaction 1",
                account=account,
                date=datetime(2023, 1, 1, tzinfo=pytz.UTC),
                user=self.user,
            ),
        ]

        Transaction.objects.bulk_create(transactions)

        url = reverse("transactions-list") + "?exclude_same_currency_exchanges=true"
        response = self.client.get(url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()["results"]), 2)
        self.assertEqual(
            response.json()["results"][0]["description"], self.data["description"]
        )
        self.assertEqual(response.json()["results"][1]["description"], "transaction 1")

    # CURRENCY EXCHANGES

    # to create a Currency exchange the endpoint should create 2 related transactions
    def test_api_create_currency_exchange(self):
        # delete the initial transaction
        Transaction.objects.get().delete()
        to_currency = Currency.objects.create(name="VES", symbol="bs")
        from_account = self.account
        to_account = Account.objects.create(name="Mercantil", currency=to_currency)
        data_payload = {
            "from_amount": "50.50",
            "to_amount": 1250,
            "description": "Exchange USD to VES",
            "from_account": from_account.id,
            "to_account": to_account.id,
            "date": datetime.now(tz=timezone.utc),
        }
        response = self.client.post(
            reverse("exchanges-list"), data_payload, format="json"
        )
        transaction_response = response.json()
        response_from = CurrencyExchange.objects.get(pk=transaction_response[0]["id"])
        response_to = CurrencyExchange.objects.get(pk=transaction_response[1]["id"])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CurrencyExchange.objects.count(), 2)
        # created with the correct amounts
        self.assertEqual(response_from.amount, -5050)
        self.assertEqual(response_to.amount, 125000)
        # created with the correct accounts
        self.assertEqual(response_from.account, from_account)
        self.assertEqual(response_to.account, to_account)
        # check both transactions are related
        self.assertEqual(response_from.related_transaction, response_to)
        self.assertEqual(response_to.related_transaction, response_from)
        # created with the correct dates
        self.assertEqual(response_from.date, data_payload["date"])
        self.assertEqual(response_to.date, data_payload["date"])
        # created with correct types
        self.assertEqual(response_from.type, "from_different_currency")
        self.assertEqual(response_to.type, "to_different_currency")

    def test_api_create_currency_exchange_unauthorized(self):
        # delete the initial transaction
        Transaction.objects.get().delete()
        to_currency = Currency.objects.create(name="VES", symbol="bs")
        from_account = self.account
        to_account = Account.objects.create(name="Mercantil", currency=to_currency)
        data_payload = {
            "from_amount": "50.50",
            "to_amount": 1250,
            "description": "Exchange USD to VES",
            "from_account": from_account.id,
            "to_account": to_account.id,
            "date": datetime.now(tz=timezone.utc),
        }
        self.client.credentials(HTTP_AUTHORIZATION=None)
        response = self.client.post(
            reverse("exchanges-list"), data_payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_api_create_transaction_with_default_description(self):
        # the default description should be "Exchange from {from_account_name} to {to_account_name}"
        to_currency = Currency.objects.create(name="VES", symbol="bs")
        from_account = self.account
        to_account = Account.objects.create(name="Mercantil", currency=to_currency)
        data_payload = {
            "from_amount": "50.5",
            "to_amount": 1250,
            "from_account": from_account.id,
            "to_account": to_account.id,
            "date": datetime.now(tz=timezone.utc),
        }
        response = self.client.post(
            reverse("exchanges-list"), data_payload, format="json"
        )
        transaction_response = response.json()
        response_from = CurrencyExchange.objects.get(pk=transaction_response[0]["id"])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response_from.description,
            f"Exchange from {from_account.name} to {to_account.name}",
        )

    def test_api_create_transaction_and_sets_type(self):
        # the type should be from_same_currency if the from_account and to_account are the same currency
        from_account = self.account
        to_currency = Currency.objects.create(name="USD")
        to_account = Account.objects.create(name="Mercantil", currency=to_currency)
        data_payload = {
            "from_amount": "50.5",
            "to_amount": 1250,
            "from_account": from_account.id,
            "to_account": to_account.id,
            "date": datetime.now(tz=timezone.utc),
        }
        response = self.client.post(
            reverse("exchanges-list"), data_payload, format="json"
        )
        transaction_response = response.json()
        response_from = CurrencyExchange.objects.get(pk=transaction_response[0]["id"])
        response_to = CurrencyExchange.objects.get(pk=transaction_response[1]["id"])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response_from.type, "from_different_currency")
        self.assertEqual(response_to.type, "to_different_currency")

    def test_api_create_transactions_and_comission_when_same_currency_exchange(self):
        # the endpoint should create a comission transaction
        # when the from_account and to_account are the same currency
        from_account = self.account
        to_account = Account.objects.create(name="Mercantil", currency=self.currency)
        data_payload = {
            "from_amount": "1250",
            "to_amount": "1200",
            "from_account": from_account.id,
            "to_account": to_account.id,
            "date": datetime.now(tz=timezone.utc),
        }
        response = self.client.post(
            reverse("exchanges-list"), data_payload, format="json"
        )
        transaction_response = response.json()
        response_from = CurrencyExchange.objects.get(pk=transaction_response[0]["id"])
        response_to = CurrencyExchange.objects.get(pk=transaction_response[1]["id"])
        response_comission = ExchangeComission.objects.get(
            pk=transaction_response[2]["id"]
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response_from.type, "from_same_currency")
        self.assertEqual(response_to.type, "to_same_currency")
        self.assertEqual(response_comission.type, "comission")
        # the comission transaction should be created with the correct amount
        self.assertEqual(response_comission.amount, -5000)
        # the comission transaction should be related to the other transactions
        self.assertEqual(response_comission.user, self.user)
        self.assertEqual(response_comission.exchange_from, response_from)
        self.assertEqual(response_comission.exchange_to, response_to)
        # rest the comission amount from the from_account
        # the user never sends the comission amount, it's calculated by the endpoint
        self.assertEqual(response_from.amount, -120000)
        self.assertEqual(response_to.amount, 120000)

    def test_api_create_transactions_and_profit_when_same_currency_exchange(self):
        # when to_amount is greater than from_amount, the endpoint should
        # create a profit transaction on the destination account
        from_account = self.account
        to_account = Account.objects.create(name="Mercantil", currency=self.currency)
        category_profit = Category.objects.create(
            name="Profits", color="#000000", description="Profits"
        )
        data_payload = {
            "from_amount": "1200",
            "to_amount": "1250",
            "from_account": from_account.id,
            "to_account": to_account.id,
            "date": datetime.now(tz=timezone.utc),
        }
        response = self.client.post(
            reverse("exchanges-list"), data_payload, format="json"
        )
        transaction_response = response.json()
        response_from = CurrencyExchange.objects.get(pk=transaction_response[0]["id"])
        response_to = CurrencyExchange.objects.get(pk=transaction_response[1]["id"])
        response_profit = ExchangeComission.objects.get(
            pk=transaction_response[2]["id"]
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response_from.type, "from_same_currency")
        self.assertEqual(response_to.type, "to_same_currency")
        self.assertEqual(response_profit.type, "profit")
        self.assertEqual(response_profit.amount, 5000)
        self.assertEqual(response_profit.account, to_account)
        self.assertEqual(response_profit.category, category_profit)
        self.assertEqual(response_profit.user, self.user)
        self.assertEqual(response_profit.exchange_from, response_from)
        self.assertEqual(response_profit.exchange_to, response_to)
        self.assertEqual(response_from.amount, -120000)
        self.assertEqual(response_to.amount, 120000)

    def test_api_create_exchange_with_categories_if_available(self):
        # delete the initial transaction
        Transaction.objects.get().delete()
        # if categories with name "Exchanges" and "Exchanges Income" are available,
        # the endpoint should create the exchages with those tags
        category_exchanges = Category.objects.create(
            name="Exchanges", color="#000000", description="Exchanges"
        )
        category_ex_income = Category.objects.create(
            name="Exchanges Income", color="#000000", description="Exchanges Income"
        )
        Category.objects.create(
            name="Comissions", color="#000000", description="Comissions"
        )
        to_currency = Currency.objects.create(name="VES", symbol="bs")
        from_account = self.account
        to_account = Account.objects.create(name="Mercantil", currency=to_currency)
        data_payload = {
            "from_amount": "50.5",
            "to_amount": 1250,
            "from_account": from_account.id,
            "to_account": to_account.id,
            "desciption": "Exchange USD to VES",
            "date": datetime.now(tz=timezone.utc),
        }
        response = self.client.post(
            reverse("exchanges-list"), data_payload, format="json"
        )
        self.assertEqual(CurrencyExchange.objects.count(), 2)
        response_from = CurrencyExchange.objects.get(pk=response.json()[0]["id"])
        response_to = CurrencyExchange.objects.get(pk=response.json()[1]["id"])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response_from.category, category_exchanges)
        self.assertEqual(response_to.category, category_ex_income)

    def test_api_delete_currency_exchange(self):
        # delete the initial transaction
        from_account = self.account
        to_currency = Currency.objects.create(name="VES")
        to_account = Account.objects.create(name="Mercantil", currency=to_currency)
        data_payload = {
            "from_amount": -50,
            "to_amount": 1250,
            "description": "Exchange USD to VES",
            "from_account": from_account.id,
            "to_account": to_account.id,
            "date": datetime.now(),
        }
        # i'm too lazy to create 2 exchange transactions with the model, use the endpoint lol
        response_exchanges = self.client.post(
            reverse("exchanges-list"), data_payload, format="json"
        )

        transaction = response_exchanges.json()[0]

        response_delete = self.client.delete(
            reverse("transactions-detail", kwargs={"pk": transaction["id"]}),
            format="json",
        )
        self.assertEqual(response_delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(CurrencyExchange.objects.count(), 0)

    def test_api_delete_currency_exchange_unauthorized(self):
        # delete the initial transaction
        from_account = self.account
        to_currency = Currency.objects.create(name="VES")
        to_account = Account.objects.create(name="Mercantil", currency=to_currency)
        data_payload = {
            "from_amount": -50,
            "to_amount": 1250,
            "description": "Exchange USD to VES",
            "from_account": from_account.id,
            "to_account": to_account.id,
            "date": datetime.now(),
        }
        # i'm too lazy to create 2 exchange transactions with the model, use the endpoint lol
        response_exchanges = self.client.post(
            reverse("exchanges-list"), data_payload, format="json"
        )

        transaction = response_exchanges.json()[0]

        self.client.credentials(HTTP_AUTHORIZATION=None)
        response_delete = self.client.delete(
            reverse("transactions-detail", kwargs={"pk": transaction["id"]}),
            format="json",
        )
        self.assertEqual(response_delete.status_code, status.HTTP_401_UNAUTHORIZED)


class TestCategories(APITestCase):
    def setUp(self):
        self.fake = Faker(["en-US"])
        self.user = User.objects.create_user(
            email=self.fake.email(),
            username=self.fake.user_name(),
            password=self.fake.password(),
        )
        self.currency = Currency.objects.create(name="USD")
        self.account = Account.objects.create(
            name="Test Account", currency=self.currency
        )
        self.data = {
            "name": "Food",
            "description": "Food expenses",
            "color": "#000000",
            "type": "expense",
        }
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(self.user).access_token}"
        )
        self.response = self.client.post(
            reverse("categories-list"), self.data, format="json"
        )

    def test_api_create_user_category(self):
        self.assertEqual(self.response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.response.json()[0]["name"], "Food")
        self.assertEqual(self.response.json()[0]["description"], "Food expenses")
        self.assertEqual(self.response.json()[0]["color"], "#000000")
        self.assertEqual(self.response.json()[0]["parent_category"], None)
        self.assertEqual(self.response.json()[0]["type"], "expense")
        category = Category.objects.get()
        self.assertEqual(Category.objects.count(), 1)
        self.assertEqual(category.user, self.user)

    def test_api_user_create_category_unauthorized(self):
        data = {
            "name": "Food",
            "description": "Food expenses",
            "color": "#000000",
            "type": "expense",
        }
        self.client.credentials(HTTP_AUTHORIZATION=None)
        response = self.client.post(reverse("categories-list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_api_create_category_with_parent(self):
        parent = {
            "name": "Food",
            "description": "Food expenses",
            "color": "#000000",
            "type": "expense",
        }
        parent_response = self.client.post(
            reverse("categories-list"), parent, format="json"
        )
        parent_id = parent_response.json()[0]["id"]
        data = {
            "name": "Groceries",
            "description": "Groceries expenses",
            "color": "#000000",
            "parent_category": parent_id,
        }
        response = self.client.post(reverse("categories-list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()[0]["name"], "Groceries")
        self.assertEqual(response.json()[0]["description"], "Groceries expenses")
        self.assertEqual(response.json()[0]["color"], "#000000")
        self.assertEqual(response.json()[0]["parent_category"], parent_id)
        self.assertEqual(response.json()[0]["type"], "expense")

    def test_get_categories(self):
        """ "Should return global and user categories"""
        # global category
        CategoryFactory(user=None)

        response = self.client.get(reverse("categories-list"), format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 2)
        self.assertEqual(response.json()[0]["name"], "Food")
        self.assertEqual(response.json()[0]["description"], "Food expenses")
        self.assertEqual(response.json()[0]["color"], "#000000")
        self.assertEqual(response.json()[0]["parent_category"], None)
        self.assertEqual(response.json()[0]["type"], "expense")

    def test_api_update_category(self):
        data = {
            "name": "Food",
            "description": "Food expenses",
            "color": "#000000",
            "type": "expense",
            "user": self.user.id,
        }
        response = self.client.post(reverse("categories-list"), data, format="json")
        category = response.json()[0]
        data = {
            "name": "Groceries",
            "description": "Groceries expenses",
            "color": "#000000",
            "type": "expense",
        }
        response = self.client.put(
            reverse("categories-detail", kwargs={"pk": category["id"]}),
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["name"], "Groceries")
        self.assertEqual(response.json()["description"], "Groceries expenses")
        self.assertEqual(response.json()["color"], "#000000")
        self.assertEqual(response.json()["parent_category"], None)
        self.assertEqual(response.json()["type"], "expense")

    def test_api_update_category_forbidden_global_category(self):
        global_category = CategoryFactory(user=None)

        user = User.objects.create_user(
            email=self.fake.email(),
            username=self.fake.user_name(),
            password=self.fake.password(),
        )

        token = RefreshToken.for_user(user)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")

        data = {
            "name": "Groceries",
            "description": "Groceries expenses",
            "color": "#000000",
            "type": "expense",
        }

        response = self.client.put(
            reverse("categories-detail", kwargs={"pk": global_category.id}),
            data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_api_update_category_forbidden_other_user_category(self):
        user = User.objects.create_user(
            email=self.fake.email(),
            username=self.fake.user_name(),
            password=self.fake.password(),
        )

        token = RefreshToken.for_user(user)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")

        data = {
            "name": "Groceries",
            "description": "Groceries expenses",
            "color": "#000000",
            "type": "expense",
        }

        category = CategoryFactory(user=self.user)

        response = self.client.put(
            reverse("categories-detail", kwargs={"pk": category.id}),
            data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_api_cant_delete_global_category(self):
        global_category = CategoryFactory(user=None)

        response = self.client.delete(
            reverse("categories-detail", kwargs={"pk": global_category.id}),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_api_cant_delete_other_user_category(self):
        category = CategoryFactory(user=self.user)

        user = User.objects.create_user(
            email=self.fake.email(),
            username=self.fake.user_name(),
            password=self.fake.password(),
        )

        token = RefreshToken.for_user(user)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")

        response = self.client.delete(
            reverse("categories-detail", kwargs={"pk": category.id}), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TestTransactionGroups(APITestCase):
    def setUp(self):
        self.fake = Faker(["en-US"])
        self.user = User.objects.create_user(
            email=self.fake.email(),
            username=self.fake.user_name(),
            password=self.fake.password(),
        )
        self.other_user = User.objects.create_user(
            email=self.fake.email(),
            username=self.fake.user_name(),
            password=self.fake.password(),
        )
        self.token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token.access_token}")

        self.currency = Currency.objects.create(
            name="VES", default_conversion_source="paralelo"
        )
        self.account = Account.objects.create(
            name="Test Account",
            currency=self.currency,
            decimal_places=2,
            user=self.user,
        )
        self.category = Category.objects.create(
            name="Food", color="#000000", description="Food expenses"
        )
        self.main_currency = CurrencyFactory(name="USD")
        self.current_conversion = CurrencyConversionHistorialFactory(
            currency_from=self.currency,
            currency_to=self.main_currency,
            date=datetime.now(tz=timezone.utc),
            rate=60,
            source="paralelo",
        )
        self.now = datetime.now(tz=timezone.utc)

    def _tx_payload(self, amount, description, date=None):
        return {
            "amount": amount,
            "description": description,
            "account": self.account.id,
            "date": date or self.now,
            "category": self.category.id,
        }

    def test_create_transactions_as_new_group(self):
        payload = {
            "group": True,
            "name": "Supermarket trip",
            "transactions": [
                self._tx_payload(-50, "Milk"),
                self._tx_payload(-30, "Bread"),
            ],
        }
        response = self.client.post(
            reverse("transactions-list"), payload, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.json()), 2)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(TransactionGroup.objects.count(), 1)

        group = TransactionGroup.objects.get()
        self.assertEqual(group.name, "Supermarket trip")
        self.assertEqual(group.user, self.user)
        for item in response.json():
            self.assertEqual(item["group"], group.id)
            self.assertEqual(item["type"], "transaction")

        members = Transaction.objects.filter(group=group)
        self.assertEqual(members.count(), 2)

    def test_create_group_defaults_name_from_first_description(self):
        payload = {
            "group": True,
            "transactions": [
                self._tx_payload(-10, "First item"),
                self._tx_payload(-20, "Second item"),
            ],
        }
        response = self.client.post(
            reverse("transactions-list"), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TransactionGroup.objects.get().name, "First item")

    def test_create_group_defaults_date_to_oldest_transaction(self):
        older = self.now - timedelta(days=3)
        newer = self.now
        payload = {
            "group": True,
            "name": "Trip",
            "transactions": [
                self._tx_payload(-10, "Newer", date=newer),
                self._tx_payload(-20, "Older", date=older),
            ],
        }
        response = self.client.post(
            reverse("transactions-list"), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        group = TransactionGroup.objects.get()
        self.assertEqual(group.date, older)

    def test_create_group_accepts_optional_explicit_date(self):
        older = self.now - timedelta(days=3)
        explicit = self.now - timedelta(days=1)
        payload = {
            "group": True,
            "name": "Trip",
            "date": explicit,
            "transactions": [
                self._tx_payload(-10, "A", date=self.now),
                self._tx_payload(-20, "B", date=older),
            ],
        }
        response = self.client.post(
            reverse("transactions-list"), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TransactionGroup.objects.get().date, explicit)

    def test_create_group_empty_transactions_returns_400(self):
        payload = {"group": True, "name": "Empty", "transactions": []}
        response = self.client.post(
            reverse("transactions-list"), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(TransactionGroup.objects.count(), 0)

    def test_create_group_from_existing_transaction_ids(self):
        older = self.now - timedelta(days=2)
        tx_a = self.client.post(
            reverse("transactions-list"),
            self._tx_payload(-50, "Milk", date=older),
            format="json",
        ).json()[0]
        tx_b = self.client.post(
            reverse("transactions-list"),
            self._tx_payload(-30, "Bread", date=self.now),
            format="json",
        ).json()[0]

        response = self.client.post(
            reverse("transactions-list"),
            {
                "group": True,
                "name": "Supermarket",
                "transactions": [tx_a["id"], tx_b["id"]],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.json()), 2)
        self.assertEqual(TransactionGroup.objects.count(), 1)
        group = TransactionGroup.objects.get()
        self.assertEqual(group.name, "Supermarket")
        self.assertEqual(group.date, older)
        self.assertEqual(
            set(Transaction.objects.filter(group=group).values_list("id", flat=True)),
            {tx_a["id"], tx_b["id"]},
        )
        self.assertTrue(all(item["group"] == group.id for item in response.json()))

    def test_create_group_from_unknown_ids_returns_400(self):
        response = self.client.post(
            reverse("transactions-list"),
            {"group": True, "name": "Bad", "transactions": [999999]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(TransactionGroup.objects.count(), 0)

    def test_create_group_mixed_ids_and_objects_returns_400(self):
        response = self.client.post(
            reverse("transactions-list"),
            {
                "group": True,
                "name": "Mixed",
                "transactions": [1, self._tx_payload(-10, "Nope")],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(TransactionGroup.objects.count(), 0)

    def test_bind_transaction_to_existing_group(self):
        group = TransactionGroup.objects.create(
            user=self.user, name="Existing", date=self.now
        )
        payload = self._tx_payload(-15, "Bound item")
        payload["group_id"] = group.id

        response = self.client.post(
            reverse("transactions-list"), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()[0]["group"], group.id)
        self.assertEqual(Transaction.objects.get().group_id, group.id)

    def test_bind_to_other_users_group_returns_400(self):
        other_group = TransactionGroup.objects.create(
            user=self.other_user, name="Other", date=self.now
        )
        payload = self._tx_payload(-15, "Bad bind")
        payload["group_id"] = other_group.id

        response = self.client.post(
            reverse("transactions-list"), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_list_collapses_grouped_transactions(self):
        # ungrouped
        self.client.post(
            reverse("transactions-list"),
            self._tx_payload(-5, "Solo", date=self.now - timedelta(hours=1)),
            format="json",
        )
        # grouped
        self.client.post(
            reverse("transactions-list"),
            {
                "group": True,
                "name": "Trip",
                "transactions": [
                    self._tx_payload(-50, "A", date=self.now),
                    self._tx_payload(-30, "B", date=self.now),
                ],
            },
            format="json",
        )

        response = self.client.get(reverse("transactions-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json()["results"]
        self.assertEqual(len(results), 2)

        types = {r["type"] for r in results}
        self.assertEqual(types, {"transaction", "group"})

        group_row = next(r for r in results if r["type"] == "group")
        self.assertEqual(group_row["name"], "Trip")
        self.assertEqual(group_row["transaction_count"], 2)
        # -50 => -83 cents, -30 => -50 cents => -1.33
        self.assertEqual(group_row["total_main_currency_amount"], "-1.33")
        # single non-USD currency: also expose original-currency total
        self.assertEqual(group_row["total_amount"], "-80.00")
        self.assertEqual(group_row["currency"], "VES")

        solo = next(r for r in results if r["type"] == "transaction")
        self.assertEqual(solo["description"], "Solo")
        self.assertIsNone(solo["group"])

    def test_list_group_omits_total_amount_for_usd_only_group(self):
        usd_account = Account.objects.create(
            name="USD Account",
            currency=self.main_currency,
            decimal_places=2,
            user=self.user,
        )
        self.client.post(
            reverse("transactions-list"),
            {
                "group": True,
                "name": "USD Trip",
                "transactions": [
                    {
                        "amount": -10,
                        "description": "A",
                        "account": usd_account.id,
                        "date": self.now,
                        "category": self.category.id,
                    },
                    {
                        "amount": -20,
                        "description": "B",
                        "account": usd_account.id,
                        "date": self.now,
                        "category": self.category.id,
                    },
                ],
            },
            format="json",
        )

        response = self.client.get(reverse("transactions-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        group_row = next(r for r in response.json()["results"] if r["type"] == "group")
        self.assertEqual(group_row["name"], "USD Trip")
        self.assertIsNone(group_row["total_amount"])
        self.assertIsNone(group_row["currency"])

    def test_list_group_omits_total_amount_for_mixed_currency_group(self):
        usd_account = Account.objects.create(
            name="USD Account",
            currency=self.main_currency,
            decimal_places=2,
            user=self.user,
        )
        tx_ves = self.client.post(
            reverse("transactions-list"),
            self._tx_payload(-50, "VES item"),
            format="json",
        ).json()[0]
        tx_usd = self.client.post(
            reverse("transactions-list"),
            {
                "amount": -10,
                "description": "USD item",
                "account": usd_account.id,
                "date": self.now,
                "category": self.category.id,
            },
            format="json",
        ).json()[0]

        self.client.post(
            reverse("transactions-list"),
            {
                "group": True,
                "name": "Mixed",
                "transactions": [tx_ves["id"], tx_usd["id"]],
            },
            format="json",
        )

        response = self.client.get(reverse("transactions-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        group_row = next(r for r in response.json()["results"] if r["type"] == "group")
        self.assertEqual(group_row["name"], "Mixed")
        self.assertIsNone(group_row["total_amount"])
        self.assertIsNone(group_row["currency"])

    def test_filter_by_group_returns_members(self):
        create_resp = self.client.post(
            reverse("transactions-list"),
            {
                "group": True,
                "name": "Trip",
                "transactions": [
                    self._tx_payload(-50, "A"),
                    self._tx_payload(-30, "B"),
                ],
            },
            format="json",
        )
        group_id = create_resp.json()[0]["group"]
        # another ungrouped tx should not appear
        self.client.post(
            reverse("transactions-list"),
            self._tx_payload(-5, "Solo"),
            format="json",
        )

        response = self.client.get(
            reverse("transactions-list") + f"?group={group_id}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json()["results"]
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["type"] == "transaction" for r in results))
        self.assertTrue(all(r["group"] == group_id for r in results))
        descriptions = {r["description"] for r in results}
        self.assertEqual(descriptions, {"A", "B"})

    def test_grouped_transactions_do_not_affect_balance(self):
        # baseline balance via ungrouped creates of same amounts
        self.client.post(
            reverse("transactions-list"),
            {
                "group": True,
                "name": "Trip",
                "transactions": [
                    self._tx_payload(-50, "A"),
                    self._tx_payload(-30, "B"),
                ],
            },
            format="json",
        )
        response = self.client.get(
            reverse("accounts-detail", kwargs={"pk": self.account.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # -50.00 + -30.00 = -80.00
        self.assertEqual(response.json()["balance"], "-80.00")

    def test_deleting_last_member_deletes_empty_group(self):
        create_resp = self.client.post(
            reverse("transactions-list"),
            {
                "group": True,
                "name": "Single",
                "transactions": [self._tx_payload(-10, "Only")],
            },
            format="json",
        )
        tx_id = create_resp.json()[0]["id"]
        group_id = create_resp.json()[0]["group"]
        self.assertTrue(TransactionGroup.objects.filter(pk=group_id).exists())

        response = self.client.delete(
            reverse("transactions-detail", kwargs={"pk": tx_id})
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(TransactionGroup.objects.filter(pk=group_id).exists())

