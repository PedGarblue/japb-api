import pytz
from faker import Faker
from datetime import datetime, timezone
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Transaction, CurrencyExchange, ExchangeComission, Category
from .factories import TransactionFactory
from japb_api.accounts.models import Account
from japb_api.currencies.models import Currency

class TestCurrencyTransaction(APITestCase):
    def setUp(self):
        self.fake = Faker(['en-US'])
        self.currency = Currency.objects.create(name = 'USD')
        self.account = Account.objects.create(name = 'Test Account', currency = self.currency)
        self.category = Category.objects.create(name = 'Food', color = '#000000', description = 'Food expenses')
        self.data = {
            'amount': -50,
            'description': 'Purchase',
            'account': self.account.id,
            'date': datetime.now(tz=timezone.utc),
            'category': self.category.id
        }
        self.data2 = {
            'amount': -30,
            'description': 'Purchase2',
            'account': self.account.id,
            'date': datetime.now(tz=timezone.utc),
            'category': self.category.id
        }
        self.data3 = {
            'amount': -500,
            'description': 'Purchase3',
            'account': self.account.id,
            'date': datetime.now(tz=timezone.utc),
            'category': self.category.id
        }

        self.response = self.client.post(
            reverse('transactions-list'),
            self.data,
            format = 'json'
        )

    def test_api_create_transaction(self):
        self.assertEqual(self.response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Transaction.objects.count(), 1)
        transaction = Transaction.objects.get()
        self.assertEqual(transaction.description, 'Purchase')
        self.assertEqual(transaction.category, self.category)
        self.assertEqual(transaction.amount, -5000)

    def test_api_create_transaction_handles_decimal_places(self):
        Transaction.objects.all().delete()
        # create an account with 3 decimal places
        account = Account.objects.create(name = 'Binance BTC', currency = self.currency, decimal_places = 8)
        data = {
            'amount': 0.00040000,
            'description': 'Purchase',
            'account': account.id,
            'date': datetime.now(tz=timezone.utc),
        }
        response = self.client.post(
            reverse('transactions-list'),
            data,
            format = 'json'
        )
        transaction = Transaction.objects.get()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Transaction.objects.count(), 1)
        # the amount should be saved as integer when the account decimal place are greater than 2
        # in the account serializer, the amount is divided by 10 ** account.decimal_places
        self.assertEqual(transaction.amount, 40000)

    def test_api_create_multiple_transactions(self):
        data = [self.data, self.data2, self.data3]
        response = self.client.post(
            reverse('transactions-list'),
            data,
            format = 'json'
        )

        self.assertEqual(self.response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.response.json()[0]['amount'], '-50.00')
        # 3 + the one created at setUp()
        self.assertEqual(Transaction.objects.count(), 4)
    
    def test_api_get_transactions(self):
        url = reverse('transactions-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Transaction.objects.count(), 1)
        # amount
        self.assertEquals(response.json()[0]['amount'], '-50.00')
        self.assertEquals(response.json()[0]['category'], self.category.id)

    def test_api_get_a_transaction(self):
        transaction = Transaction.objects.get()
        response = self.client.get(reverse('transactions-detail', kwargs={ 'pk': transaction.id }), format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['amount'], '-50.00')
        self.assertEquals(response.json()['category'], self.category.id)
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
        self.assertEqual(updated_transaction.amount, -500)

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
    
    def test_api_get_transaction_by_datetime(self):
        # add transacions to the account
        account = self.account
        transactions = [
            Transaction(amount=10, description="transaction 1", account=account, date=datetime(2023, 1, 1, tzinfo=pytz.UTC)),
            Transaction(amount=30, description="transaction 2", account=account, date=datetime(2023, 3, 1, tzinfo=pytz.UTC)),
            Transaction(amount=25, description="transaction 3", account=account, date=datetime(2023, 3, 1, tzinfo=pytz.UTC))
        ]
        Transaction.objects.bulk_create(transactions) 

        url = reverse('transactions-list') + '?start_date=2023-03-01T00:00:00Z&end_date=2023-03-01T23:59:59Z'
        response = self.client.get(url, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Transaction.objects.count(), 4)
        self.assertEqual(len(response.json()), 2)
        self.assertEqual(response.json()[0]['description'], 'transaction 2')
        self.assertEqual(response.json()[1]['description'], 'transaction 3')

    def test_api_get_transaction_by_account(self):
        # add transacions to the account
        account = self.account
        account2 = Account.objects.create(name = 'Test Account 2', currency = self.currency)
        transactions = [
            Transaction(amount=10, description="transaction 1", account=account, date=datetime(2023, 1, 1, tzinfo=pytz.UTC)),
            Transaction(amount=30, description="transaction 2", account=account, date=datetime(2023, 3, 1, tzinfo=pytz.UTC)),
            Transaction(amount=25, description="transaction 3", account=account2, date=datetime(2023, 3, 1, tzinfo=pytz.UTC))
        ]
        Transaction.objects.bulk_create(transactions) 

        url = reverse('transactions-list') + '?account=' + str(account.id)
        response = self.client.get(url, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 3)
        self.assertEqual(response.json()[0]['description'], 'transaction 2')
        self.assertEqual(response.json()[1]['description'], 'transaction 1')
        self.assertEqual(response.json()[2]['description'], 'Purchase')

    def test_api_get_transaction_by_currency(self):
        # add transacions to the account
        selectedCurrency = Currency.objects.create(name = 'USD')
        selectedAccount = Account.objects.create(name = 'Test Account 2', currency = selectedCurrency)
        nonSelectedCurrency = Currency.objects.create(name = 'EUR')
        account2 = Account.objects.create(name = 'Test Account 2', currency = nonSelectedCurrency)
        transactions = [
            Transaction(amount=10, description="transaction 1", account=selectedAccount, date=datetime(2023, 1, 1, tzinfo=pytz.UTC)),
            Transaction(amount=30, description="transaction 2", account=selectedAccount, date=datetime(2023, 3, 1, tzinfo=pytz.UTC)),
            Transaction(amount=40, description="transaction 3", account=selectedAccount, date=datetime(2023, 3, 1, tzinfo=pytz.UTC)),
            Transaction(amount=25, description="transaction 4", account=account2, date=datetime(2023, 3, 1, tzinfo=pytz.UTC))
        ]
        Transaction.objects.bulk_create(transactions) 

        url = reverse('transactions-list') + '?currency=' + str(selectedCurrency.id)
        response = self.client.get(url, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 3)
        self.assertEqual(response.json()[0]['description'], 'transaction 3')
        self.assertEqual(response.json()[1]['description'], 'transaction 2')
        self.assertEqual(response.json()[2]['description'], 'transaction 1')

    def test_api_get_transaction_by_exclude_same_currency_exchanges(self):
        # add transacions to the account
        account = self.account
        account2 = Account.objects.create(name = 'Test Account 2', currency = self.currency)
        ex1 = CurrencyExchange.objects.create(
            amount = -50,
            description = 'Exchange USD to USD',
            account = account,
            date = datetime(2023, 1, 1, tzinfo=pytz.UTC),
            type = 'from_same_currency'
        )
        ex2 = CurrencyExchange.objects.create(
            amount = 50,
            description = 'Exchange USD to USD',
            account = account2,
            date = datetime(2023, 1, 1, tzinfo=pytz.UTC),
            type='to_same_currency',
            related_transaction = ex1
        )
        ex1.related_transaction = ex2
        ex1.save()

        transactions = [
            Transaction(amount=10, description="transaction 1", account=account, date=datetime(2023, 1, 1, tzinfo=pytz.UTC)),
        ]

        Transaction.objects.bulk_create(transactions) 

        url = reverse('transactions-list') + '?exclude_same_currency_exchanges=true'
        response = self.client.get(url, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 2)
        self.assertEqual(response.json()[0]['description'], self.data['description'])
        self.assertEqual(response.json()[1]['description'], 'transaction 1')

    ### CURRENCY EXCHANGES

    # to create a Currency exchange the endpoint should create 2 related transactions
    def test_api_create_currency_exchange(self):
        # delete the initial transaction
        Transaction.objects.get().delete()
        to_currency = Currency.objects.create(name = 'VES', symbol="bs")
        from_account = self.account
        to_account = Account.objects.create(name = 'Mercantil', currency = to_currency)
        data_payload = {
            'from_amount': '50.50',
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
        self.assertEqual(response_from.amount, -5050)
        self.assertEqual(response_to.amount, 125000)
        # created with the correct accounts
        self.assertEqual(response_from.account, from_account)
        self.assertEqual(response_to.account, to_account)
        # check both transactions are related
        self.assertEqual(response_from.related_transaction, response_to)
        self.assertEqual(response_to.related_transaction, response_from)
        # created with the correct dates
        self.assertEqual(response_from.date, data_payload['date'])
        self.assertEqual(response_to.date, data_payload['date'])
        # created with correct types
        self.assertEqual(response_from.type, 'from_different_currency')
        self.assertEqual(response_to.type, 'to_different_currency')

    def test_api_create_transaction_with_default_description(self):
        # the default description should be "Exchange from {from_account_name} to {to_account_name}"
        to_currency = Currency.objects.create(name = 'VES', symbol="bs")
        from_account = self.account
        to_account = Account.objects.create(name = 'Mercantil', currency = to_currency)
        data_payload = {
            'from_amount': '50.5',
            'to_amount': 1250,
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
        self.assertEqual(response_from.description, f"Exchange from {from_account.name} to {to_account.name}")
    
    def test_api_create_transaction_and_sets_type(self):
        # the type should be from_same_currency if the from_account and to_account are the same currency
        from_account = self.account
        to_currency = Currency.objects.create(name = 'USD')
        to_account = Account.objects.create(name = 'Mercantil', currency = to_currency)
        data_payload = {
            'from_amount': '50.5',
            'to_amount': 1250,
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
        self.assertEqual(response_from.type, 'from_different_currency')
        self.assertEqual(response_to.type, 'to_different_currency')
        
    def test_api_create_transactions_and_comission_when_same_currency_exchange(self):
        # the endpoint should create a comission transaction when the from_account and to_account are the same currency
        from_account = self.account
        to_account = Account.objects.create(name = 'Mercantil', currency = self.currency)
        data_payload = {
            'from_amount': '1250',
            'to_amount': '1200',
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
        response_comission = ExchangeComission.objects.get(pk=transaction_response[2]['id'])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response_from.type, 'from_same_currency')
        self.assertEqual(response_to.type, 'to_same_currency')
        self.assertEqual(response_comission.type, 'comission')
        # the comission transaction should be created with the correct amount
        self.assertEqual(response_comission.amount, -5000)
        # the comission transaction should be related to the other transactions
        self.assertEqual(response_comission.exchange_from, response_from)
        self.assertEqual(response_comission.exchange_to, response_to)
        # rest the comission amount from the from_account
        # the user never sends the comission amount, it's calculated by the endpoint
        self.assertEqual(response_from.amount, -120000)
        self.assertEqual(response_to.amount, 120000)

    def test_api_create_exchange_with_categories_if_available(self):
        # delete the initial transaction
        Transaction.objects.get().delete()
        # if categories with name "Exchanges" and "Exchanges Income" are available, the endpoint should create the exchages with those tags
        category_exchanges = Category.objects.create(name = 'Exchanges', color = '#000000', description = 'Exchanges')
        category_ex_income = Category.objects.create(name = 'Exchanges Income', color = '#000000', description = 'Exchanges Income')
        Category.objects.create(name = 'Comissions', color = '#000000', description = 'Comissions')
        to_currency = Currency.objects.create(name = 'VES', symbol="bs")
        from_account = self.account
        to_account = Account.objects.create(name = 'Mercantil', currency = to_currency)
        data_payload = {
            'from_amount': '50.5',
            'to_amount': 1250,
            'from_account': from_account.id,
            'to_account': to_account.id,
            'desciption': 'Exchange USD to VES',
            'date': datetime.now(tz=timezone.utc),
        }
        response = self.client.post(
            reverse('exchanges-list'),
            data_payload,
            format = 'json'
        )
        self.assertEqual(CurrencyExchange.objects.count(), 2)
        response_from = CurrencyExchange.objects.get(pk=response.json()[0]['id'])
        response_to = CurrencyExchange.objects.get(pk=response.json()[1]['id'])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response_from.category, category_exchanges)
        self.assertEqual(response_to.category, category_ex_income)

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
        
class TestCategories(APITestCase):
    def setUp(self):
        self.fake = Faker(['en-US'])
        self.currency = Currency.objects.create(name = 'USD')
        self.account = Account.objects.create(name = 'Test Account', currency = self.currency)
        self.data = {
            'amount': -50,
            'description': 'Purchase',
            'account': self.account.id,
            'type': 'expense',
            'date': datetime.now(tz=timezone.utc),
        }
        self.response = self.client.post(
            reverse('transactions-list'),
            self.data,
            format = 'json'
        )

    def test_api_create_category(self):
        data = {
            'name': 'Food',
            'description': 'Food expenses',
            'color': '#000000',
            'type': 'expense',
        }
        response = self.client.post(
            reverse('categories-list'),
            data,
            format = 'json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()[0]['name'], 'Food')
        self.assertEqual(response.json()[0]['description'], 'Food expenses')
        self.assertEqual(response.json()[0]['color'], '#000000')
        self.assertEqual(response.json()[0]['parent_category'], None)
        self.assertEqual(response.json()[0]['type'], 'expense')

    def test_api_create_category_with_parent(self):
        parent = {
            'name': 'Food',
            'description': 'Food expenses',
            'color': '#000000',
            'type': 'expense',
        }
        parent_response = self.client.post(
            reverse('categories-list'),
            parent,
            format = 'json'
        )
        parent_id = parent_response.json()[0]['id']
        data = {
            'name': 'Groceries',
            'description': 'Groceries expenses',
            'color': '#000000',
            'parent_category': parent_id
        }
        response = self.client.post(
            reverse('categories-list'),
            data,
            format = 'json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()[0]['name'], 'Groceries')
        self.assertEqual(response.json()[0]['description'], 'Groceries expenses')
        self.assertEqual(response.json()[0]['color'], '#000000')
        self.assertEqual(response.json()[0]['parent_category'], parent_id)
        self.assertEqual(response.json()[0]['type'], 'expense')

    def test_get_categories(self):
        data = {
            'name': 'Food',
            'description': 'Food expenses',
            'color': '#000000',
            'type': 'expense',
        }
        response = self.client.post(
            reverse('categories-list'),
            data,
            format = 'json'
        )
        response = self.client.get(reverse('categories-list'), format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()[0]['name'], 'Food')
        self.assertEqual(response.json()[0]['description'], 'Food expenses')
        self.assertEqual(response.json()[0]['color'], '#000000')
        self.assertEqual(response.json()[0]['parent_category'], None)
        self.assertEqual(response.json()[0]['type'], 'expense')