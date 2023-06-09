import pytz
from faker import Faker
from datetime import datetime, timezone
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Transaction, CurrencyExchange
from .factories import TransactionFactory
from japb_api.accounts.models import Account
from japb_api.accounts.models import Currency

class TestCurrencyTransaction(APITestCase):
    def setUp(self):
        self.fake = Faker(['en-US'])
        self.currency = Currency.objects.create(name = 'USD')
        self.account = Account.objects.create(name = 'Test Account', currency = self.currency)
        self.data = {
            'amount': -50,
            'description': 'Purchase',
            'account': self.account.id,
            'date': datetime.now(tz=timezone.utc),
        }
        self.data2 = {
            'amount': -30,
            'description': 'Purchase2',
            'account': self.account.id,
            'date': datetime.now(tz=timezone.utc),
        }
        self.data3 = {
            'amount': -500,
            'description': 'Purchase3',
            'account': self.account.id,
            'date': datetime.now(tz=timezone.utc),
        }

        self.response = self.client.post(
            reverse('transactions-list'),
            self.data,
            format = 'json'
        )

    def test_api_create_transaction(self):
        transaction = Transaction.objects.get()
        self.assertEqual(self.response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertEqual(transaction.description, 'Purchase')
        self.assertEqual(transaction.amount, -50)

    def test_api_create_multiple_transactions(self):
        data = [self.data, self.data2, self.data3]
        response = self.client.post(
            reverse('transactions-list'),
            data,
            format = 'json'
        )

        self.assertEqual(self.response.status_code, status.HTTP_201_CREATED)
        # 3 + the one created at setUp()
        self.assertEqual(Transaction.objects.count(), 4)

    def test_api_get_transactions(self):
        url = reverse('transactions-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Transaction.objects.count(), 1)

    def test_api_get_a_transaction(self):
        transaction = Transaction.objects.get()
        response = self.client.get(reverse('transactions-detail', kwargs={ 'pk': transaction.id }), format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Transaction.objects.count(), 1)

    def test_api_get_a_transaction_not_found(self):
        transaction = Transaction.objects.get()
        response = self.client.get(reverse('transactions-detail', kwargs={ 'pk': 3 }), format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_api_can_update_a_transaction(self):
        transaction = Transaction.objects.get()
        new_data = {
            'description': 'New transaction',
            'amount': -5,
            'account': self.account.id,
            'date': datetime.now(tz=timezone.utc),
        }
        response = self.client.put(reverse('transactions-detail', kwargs={ 'pk': transaction.id }), data=new_data, format='json')
        updated_transaction = Transaction.objects.get()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(updated_transaction.description, "New transaction")
        self.assertEqual(updated_transaction.amount, -5)

    def test_api_can_delete_a_transaction(self):
        transaction = Transaction.objects.get()
        response = self.client.delete(reverse('transactions-detail', kwargs={ 'pk': transaction.id }), format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_api_get_transaction_by_custom_date(self):
        # add transacions to the account
        account = self.account
        transactions = [
            Transaction(amount=10, description="transaction 1", account=account, date=datetime(2023, 1, 1, tzinfo=pytz.UTC)),
            Transaction(amount=30, description="transaction 2", account=account, date=datetime(2023, 3, 1, tzinfo=pytz.UTC)),
            Transaction(amount=25, description="transaction 3", account=account, date=datetime(2023, 3, 1, tzinfo=pytz.UTC))
        ]
        Transaction.objects.bulk_create(transactions) 

        url = reverse('transactions-list') + '?start_date=2023-02-01&end_date=2023-03-10'
        response = self.client.get(url, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Transaction.objects.count(), 4)
        self.assertEqual(len(response.json()), 2)
        self.assertEqual(response.json()[0]['description'], 'transaction 2')
        self.assertEqual(response.json()[1]['description'], 'transaction 3')

    ### CURRENCY EXCHANGES

    # to create a Currency exchange the endpoint should create 2 related transactions
    def test_api_create_currency_exchange(self):
        # delete the initial transaction
        Transaction.objects.get().delete()
        to_currency = Currency.objects.create(name = 'VES', symbol="bs")
        from_account = self.account
        to_account = Account.objects.create(name = 'Mercantil', currency = to_currency)
        data_payload = {
            'from_amount': '50.5',
            'to_amount': 1250,
            'description': 'Exchange USD to VES',
            'from_account': from_account.id,
            'to_account': to_account.id,
            'date': datetime.now(tz=timezone.utc),
        }
        response = self.client.post(
            reverse('exchanges-list'),
            data_payload,
            format = 'json'
        )
        transaction_response = response.json()
        response_from = CurrencyExchange.objects.get(pk=transaction_response[0]['id'])
        response_to = CurrencyExchange.objects.get(pk=transaction_response[1]['id'])
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CurrencyExchange.objects.count(), 2)
        # created with the correct amounts
        self.assertEqual(response_from.amount, -50.5)
        self.assertEqual(response_to.amount, 1250)
        # created with the correct accounts
        self.assertEqual(response_from.account, from_account)
        self.assertEqual(response_to.account, to_account)
        # check both transactions are related
        self.assertEqual(response_from.related_transaction, response_to)
        self.assertEqual(response_to.related_transaction, response_from)
        # created with the correct dates
        self.assertEqual(response_from.date, data_payload['date'])
        self.assertEqual(response_to.date, data_payload['date'])
        
    # should delete the 2 transactions created
    def test_api_delete_currency_exchange(self):
        # delete the initial transaction
        from_account = self.account
        to_currency = Currency.objects.create(name = 'VES')
        to_account = Account.objects.create(name = 'Mercantil', currency = to_currency)
        data_payload = {
            'from_amount': -50,
            'to_amount': 1250,
            'description': 'Exchange USD to VES',
            'from_account': from_account.id,
            'to_account': to_account.id,
            'date': datetime.now(),
        }
        # i'm too lazy to create 2 exchange transactions with the model, use the endpoint lol
        response_exchanges = self.client.post(
            reverse('exchanges-list'),
            data_payload,
            format = 'json'
        )

        transaction = response_exchanges.json()[0]

        response_delete = self.client.delete(reverse('transactions-detail', kwargs={ 'pk': transaction['id'] }), format='json')
        self.assertEqual(response_delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(CurrencyExchange.objects.count(), 0)
        
