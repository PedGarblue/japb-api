import pytz
from faker import Faker
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from japb_api.users.factories import UserFactory
from japb_api.currencies.models import Currency
from japb_api.transactions.models import Transaction
from japb_api.transactions.factories import TransactionFactory
from ..models import Account


# /accounts/ endpoints
class TestAccountsViews(APITestCase):
    def setUp(self):
        self.fake = Faker(["en-US"])
        self.currency = Currency.objects.create(name="USD")
        self.user = UserFactory(password="password1234")
        self.token = RefreshToken.for_user(self.user)
        self.data = {
            "name": "Test Account",
            "currency": self.currency.id,
            "decimal_places": "2",
        }

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token.access_token}")
        self.response = self.client.post(
            reverse("accounts-list"), self.data, format="json"
        )

    def test_api_create_account(self):
        self.assertEquals(self.response.status_code, status.HTTP_201_CREATED)
        self.assertEquals(Account.objects.count(), 1)
        accountdb = Account.objects.get()
        self.assertEquals(accountdb.name, "Test Account")
        self.assertEquals(accountdb.currency, self.currency)
        self.assertEquals(accountdb.decimal_places, 2)
        self.assertEquals(f"{accountdb.user.id}", self.user.id)

    def test_api_create_account_without_optional_params(self):
        # clean up
        Account.objects.all().delete()

        data = {
            "name": "Test Account",
            "currency": self.currency.id,
        }
        response = self.client.post(reverse("accounts-list"), data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Account.objects.count(), 1)
        self.assertEqual(Account.objects.get().decimal_places, 2)

    def test_api_get_accounts(self):
        nonuser = UserFactory()
        nonuserAccount = Account.objects.create(
            name="Non User Account", currency=self.currency, user=nonuser
        )

        url = reverse("accounts-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["results"][0]["name"], self.data["name"])

    def test_api_get_a_account(self):
        account = Account.objects.get()

        response = self.client.get(
            reverse("accounts-detail", kwargs={"pk": account.id}), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["name"], "Test Account")
        self.assertEqual(Account.objects.count(), 1)

    def test_api_get_a_account_not_found(self):
        response = self.client.get(
            reverse("accounts-detail", kwargs={"pk": 999}), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_api_cant_access_other_user_account(self):
        nonuser = UserFactory()
        nonuserAccount = Account.objects.create(
            name="Non User Account", currency=self.currency, user=nonuser
        )
        response = self.client.get(
            reverse("accounts-detail", kwargs={"pk": nonuserAccount.id}), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_api_can_update_a_account(self):
        account = Account.objects.get()
        new_data = {
            "name": "New Test Account",
            "currency": self.currency.id,
        }
        response = self.client.put(
            reverse("accounts-detail", kwargs={"pk": account.id}),
            data=new_data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Account.objects.get().name, "New Test Account")

    def test_api_cant_update_other_user_account(self):
        nonuser = UserFactory()
        nonuserAccount = Account.objects.create(
            name="Non User Account", currency=self.currency, user=nonuser
        )
        new_data = {
            "name": "New Test Account",
            "currency": self.currency.id,
        }
        response = self.client.put(
            reverse("accounts-detail", kwargs={"pk": nonuserAccount.id}),
            data=new_data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_api_can_delete_a_account(self):
        account = Account.objects.get()
        response = self.client.delete(
            reverse("accounts-detail", kwargs={"pk": account.id}), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Account.objects.count(), 0)

    def test_api_cant_delete_other_user_account(self):
        nonuser = UserFactory()
        nonuserAccount = Account.objects.create(
            name="Non User Account", currency=self.currency, user=nonuser
        )
        response = self.client.delete(
            reverse("accounts-detail", kwargs={"pk": nonuserAccount.id}), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_api_accounts_list_show_balances(self):
        account = Account.objects.get()
        TransactionFactory(
            amount=1064,
            description="transaction 1",
            account=account,
            user=self.user,
            date=self.fake.date_time(tzinfo=pytz.UTC),
        ),
        TransactionFactory(
            amount=3046,
            description="transaction 2",
            account=account,
            user=self.user,
            date=self.fake.date_time(tzinfo=pytz.UTC),
        ),
        TransactionFactory(
            amount=-4100,
            description="transaction 3",
            account=account,
            user=self.user,
            date=self.fake.date_time(tzinfo=pytz.UTC),
        )

        url = reverse("accounts-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["results"][0]["balance"], "0.10")

    def test_api_account_detail_shows_balance(self):
        account = Account.objects.get()
        TransactionFactory(
            amount=2010,
            description="transaction 1",
            account=account,
            user=self.user,
            date=self.fake.date_time(tzinfo=pytz.UTC),
        ),
        TransactionFactory(
            amount=3050,
            description="transaction 2",
            account=account,
            user=self.user,
            date=self.fake.date_time(tzinfo=pytz.UTC),
        ),
        TransactionFactory(
            amount=-5050,
            description="transaction 3",
            account=account,
            user=self.user,
            date=self.fake.date_time(tzinfo=pytz.UTC),
        )

        response = self.client.get(
            reverse("accounts-detail", kwargs={"pk": account.id}), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["balance"], "0.10")

    def test_api_account_parses_decimals_correctly(self):
        account = Account.objects.get()
        account.decimal_places = 8
        account.save()

        # imagine btc transactions
        # 10000 satoshis = 0.00010000 btc
        TransactionFactory(
            amount=10000,
            description="transaction 1",
            account=account,
            user=self.user,
            date=self.fake.date_time(tzinfo=pytz.UTC),
        ),
        TransactionFactory(
            amount=30050,
            description="transaction 2",
            account=account,
            user=self.user,
            date=self.fake.date_time(tzinfo=pytz.UTC),
        ),
        TransactionFactory(
            amount=-15050,
            description="transaction 3",
            account=account,
            user=self.user,
            date=self.fake.date_time(tzinfo=pytz.UTC),
        )

        response = self.client.get(
            reverse("accounts-detail", kwargs={"pk": account.id}), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["balance"], "0.00025000")
