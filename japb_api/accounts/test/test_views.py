import pytz
from faker import Faker
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from japb_api.currencies.models import Currency
from japb_api.transactions.models import Transaction
from ..models import Account

# /accounts/ endpoints
class TestAccountsViews(APITestCase):
    def setUp(self):
        self.fake = Faker(['en-US'])
        self.currency = Currency.objects.create(name = 'USD')
        self.data = {
            'name': 'Test Account',
            'currency': self.currency.id,
            'decimal_places': '2'
        }
        self.response = self.client.post(
            reverse('accounts-list'),
            self.data,
            format = 'json'
        )
    
    def test_api_create_account(self):
        self.assertEqual(self.response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Account.objects.count(), 1)
        self.assertEqual(Account.objects.get().name, 'Test Account')

    def test_api_create_account_without_optional_params(self):
        # clean up
        Account.objects.all().delete()

        data = {
            'name': 'Test Account',
            'currency': self.currency.id,
        }
        response = self.client.post(
            reverse('accounts-list'),
            data,
            format = 'json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Account.objects.count(), 1)
        self.assertEqual(Account.objects.get().decimal_places, 2)

    def test_api_get_accounts(self):
        account = Account.objects.get()

        url = reverse('accounts-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Account.objects.count(), 1)
        self.assertEqual(response.json()[0]['name'], 'Test Account')

    def test_api_get_a_account(self):
        account = Account.objects.get()

        response = self.client.get(reverse('accounts-detail', kwargs={ 'pk': account.id }), format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['name'], 'Test Account')
        self.assertEqual(Account.objects.count(), 1)


    def test_api_can_update_a_account(self):
        account = Account.objects.get()
        new_data = {
            "name": "New Test Account",
            "currency": self.currency.id,
        }
        response = self.client.put(reverse('accounts-detail', kwargs={ 'pk': account.id }), data=new_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Account.objects.get().name, "New Test Account")

    def test_api_can_delete_a_account(self):
        account = Account.objects.get()
        response = self.client.delete(reverse('accounts-detail', kwargs={ 'pk': account.id }), format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Account.objects.count(), 0)

    def test_api_accounts_list_show_balances(self):
        account = Account.objects.get()
        transactions = [
            Transaction(amount=10.64, description="transaction 1", account=account, date=self.fake.date_time(tzinfo=pytz.UTC)),
            Transaction(amount=30.46, description="transaction 2", account=account, date=self.fake.date_time(tzinfo=pytz.UTC)),
            Transaction(amount=-41, description="transaction 3", account=account, date=self.fake.date_time(tzinfo=pytz.UTC))
        ]
        Transaction.objects.bulk_create(transactions) 

        url = reverse('accounts-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()[0]['balance'], '0.10')

    def test_api_account_detail_shows_balance(self):
        account = Account.objects.get()
        transactions = [
            Transaction(amount=20.10, description="transaction 1", account=account, date=self.fake.date_time(tzinfo=pytz.UTC)),
            Transaction(amount=30.50, description="transaction 2", account=account, date=self.fake.date_time(tzinfo=pytz.UTC)),
            Transaction(amount=-50.50, description="transaction 3", account=account, date=self.fake.date_time(tzinfo=pytz.UTC))
        ]
        Transaction.objects.bulk_create(transactions) 

        response = self.client.get(reverse('accounts-detail', kwargs={ 'pk': account.id }), format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['balance'], '0.10')