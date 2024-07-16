import pytz
from datetime import date
from datetime import datetime
from faker import Faker
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from ..models import ReportAccount, ReportCurrency
from japb_api.users.factories import UserFactory
from japb_api.accounts.models import Account
from japb_api.currencies.models import Currency
from japb_api.transactions.models import Transaction
from japb_api.transactions.factories import TransactionFactory, CurrencyExchangeFactory
from japb_api.reports.factories import ReportAccountFactory, ReportCurrencyFactory
from japb_api.accounts.factories import AccountFactory

class TestReportAccountViews(APITestCase):
    def setUp(self):
        self.fake = Faker(['en-US'])
        self.currency = Currency.objects.create(name='Test Currency', symbol='T')
        self.user = UserFactory()
        self.token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token.access_token}')

        self.account = Account.objects.create(name='Test Account', currency=self.currency, user = self.user)
        self.data = {
            'from_date': date(2023, 1, 1),
            'to_date': date(2023, 1, 31),
            'account': self.account.id,
        }
        self.transactions = [
            # initial balance transaction
            Transaction(
                user = self.user,
                amount= 6000,
                description="transaction initial balance",
                account=self.account,
                date=datetime(2022, 12, 30, tzinfo=pytz.UTC)
            ),
            # income transactions
            Transaction(
                user = self.user,
                amount=1064,
                description="transaction income 1",
                account=self.account,
                date=datetime(2023, 1, 1, tzinfo=pytz.UTC)
            ),
            Transaction(
                user = self.user,
                amount=3046,
                description="transaction income 2",
                account=self.account,
                date=datetime(2023,1, 3, tzinfo=pytz.UTC)
            ),
            # expense transactions
            Transaction(
                user = self.user,
                amount=-4100,
                description="transaction expense 3",
                account=self.account,
                date=datetime(2023, 1, 4, tzinfo=pytz.UTC)
            )
        ]
    
    def test_api_create_report(self):
        response = self.client.post(reverse('reports-list'), self.data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ReportAccount.objects.count(), 1)
        db_report = ReportAccount.objects.get()
        self.assertEqual(db_report.from_date, date(2023, 1, 1))
        self.assertEqual(db_report.to_date, date(2023, 1, 31))
        self.assertEqual(db_report.initial_balance, 0)
        self.assertEqual(db_report.end_balance, 0)
        self.assertEqual(db_report.total_income, 0)
        self.assertEqual(db_report.total_expenses, 0)
        self.assertEqual(db_report.account.id, self.account.id)
        self.assertEqual(f'{db_report.user.id}', self.user.id)

    def test_api_create_report_invalid_data(self):
        self.data['from_date'] = 'invalid'
        response = self.client.post(reverse('reports-list'), self.data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ReportAccount.objects.count(), 0)
    
    def test_api_create_report_invalid_account(self):
        self.data['account'] = 999
        response = self.client.post(reverse('reports-list'), self.data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ReportAccount.objects.count(), 0)
    
    def test_api_create_report_calculates_balances_income_and_expences(self):
        Transaction.objects.bulk_create(self.transactions) 
        
        self.client.post(reverse('reports-list'), self.data, format='json')
        self.assertEqual(ReportAccount.objects.count(), 1)
        db_report = ReportAccount.objects.get()

        self.assertEqual(db_report.from_date, date(2023, 1, 1))
        self.assertEqual(db_report.to_date, date(2023, 1, 31))
        self.assertEqual(db_report.initial_balance, 6000)
        self.assertEqual(db_report.end_balance, 6010)
        self.assertEqual(db_report.total_income, 4110)
        self.assertEqual(db_report.total_expenses, -4100)
        self.assertEqual(db_report.account.id, self.account.id)

    def test_api_lists_reports(self):
        Transaction.objects.bulk_create(self.transactions) 
        self.client.post(reverse('reports-list'), self.data, format='json')
        response = self.client.get(reverse('reports-list'), format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        json_data = response.json() 
        self.assertEqual(len(json_data), 1)
        self.assertEqual(json_data[0]['from_date'], '2023-01-01')
        self.assertEqual(json_data[0]['to_date'], '2023-01-31')
        self.assertEqual(json_data[0]['initial_balance'], '60.00')
        self.assertEqual(json_data[0]['end_balance'], '60.10')
        self.assertEqual(json_data[0]['balance_status'], 'positive')
        self.assertEqual(json_data[0]['total_income'], '41.10')
        self.assertEqual(json_data[0]['total_expenses'], '-41.00')

    def test_api_lists_reports_by_account(self):
        account2 = Account.objects.create(name='Test Account 2', currency=self.currency, user = self.user)
        ReportAccount.objects.create(
            user = self.user,
            from_date=date(2023, 1, 1),
            to_date=date(2023, 1, 31),
            account=account2,
        )
        Transaction.objects.bulk_create(self.transactions) 
        self.client.post(reverse('reports-list'), self.data, format='json')
        response = self.client.get(reverse('reports-list'), { 'account': self.account.id }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        json_data = response.json() 
        self.assertEqual(len(json_data), 1)
        self.assertEqual(json_data[0]['from_date'], '2023-01-01')
        self.assertEqual(json_data[0]['to_date'], '2023-01-31')
        self.assertEqual(json_data[0]['initial_balance'], '60.00')
        self.assertEqual(json_data[0]['end_balance'], '60.10')
        self.assertEqual(json_data[0]['balance_status'], 'positive')
        self.assertEqual(json_data[0]['total_income'], '41.10')
        self.assertEqual(json_data[0]['total_expenses'], '-41.00')

    def test_api_lists_and_sorts_reports_by_from_date(self):
        reports = [
            ReportAccount(
                user = self.user,
                from_date=date(2023, 1, 1),
                to_date=date(2023, 1, 31),
                account=self.account,
            ),
            ReportAccount(
                user = self.user,
                from_date=date(2023, 2, 1),
                to_date=date(2023, 2, 28),
                account=self.account,
            ),
            ReportAccount(
                user = self.user,
                from_date=date(2023, 3, 1),
                to_date=date(2023, 3, 31),
                account=self.account,
            ),
        ]
        ReportAccount.objects.bulk_create(reports)

        response = self.client.get(reverse('reports-list'), { 'ordering': '-from_date' }, format='json')
        json_data = response.json()

        self.assertEquals(len(json_data), 3)
        self.assertEquals(json_data[0]['from_date'], '2023-03-01')
        self.assertEquals(json_data[1]['from_date'], '2023-02-01')
        self.assertEquals(json_data[2]['from_date'], '2023-01-01')

    def test_api_get_report(self):
        Transaction.objects.bulk_create(self.transactions) 
        self.client.post(reverse('reports-list'), self.data, format='json')
        report = ReportAccount.objects.get()

        url = reverse('reports-detail', kwargs={ 'pk': report.id })
        response = self.client.get(url, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        json_data = response.json() 
        self.assertEqual(json_data['from_date'], '2023-01-01')
        self.assertEqual(json_data['to_date'], '2023-01-31')
        self.assertEqual(json_data['initial_balance'], '60.00')
        self.assertEqual(json_data['end_balance'], '60.10')
        self.assertEqual(json_data['balance_status'], 'positive')
        self.assertEqual(json_data['total_income'], '41.10')
        self.assertEqual(json_data['total_expenses'], '-41.00')

    def test_api_updates_report(self):
        self.client.post(reverse('reports-list'), self.data, format='json')
        report = ReportAccount.objects.get()

        url = reverse('reports-detail', kwargs={ 'pk': report.id })
        data = {
            'from_date': date(2023, 2, 1),
            'to_date': date(2023, 2, 28),
            'account': self.account.id,
        }
        response = self.client.put(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        json_data = response.json() 
        self.assertEqual(json_data['from_date'], '2023-02-01')
        self.assertEqual(json_data['to_date'], '2023-02-28')

    def test_api_updates_report_and_updates_calculations(self):
        Transaction.objects.bulk_create(self.transactions) 
        self.client.post(reverse('reports-list'), self.data, format='json')
        report = ReportAccount.objects.get()

        url = reverse('reports-detail', kwargs={ 'pk': report.id })
        data = {
            'from_date': date(2023, 1, 2),
            'to_date': date(2023, 1, 30),
            'account': self.account.id,
        }
        response = self.client.put(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        json_data = response.json() 
        self.assertEqual(json_data['from_date'], '2023-01-02')
        self.assertEqual(json_data['to_date'], '2023-01-30')
        self.assertEqual(json_data['initial_balance'], '70.64')
        self.assertEqual(json_data['end_balance'], '60.10')
        self.assertEqual(json_data['balance_status'], 'negative')
        self.assertEqual(json_data['total_income'], '30.46')
        self.assertEqual(json_data['total_expenses'], '-41.00')
    
    def test_api_deletes_report(self):
        Transaction.objects.bulk_create(self.transactions) 
        self.client.post(reverse('reports-list'), self.data, format='json')
        report = ReportAccount.objects.get()

        url = reverse('reports-detail', kwargs={ 'pk': report.id })
        response = self.client.delete(url, format='json')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(ReportAccount.objects.count(), 0)

class TestReportCurrencyViews(APITestCase):
    def setUp(self):
        self.fake = Faker(['en-US'])
        self.user = UserFactory()
        self.token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token.access_token}')
        self.currency = Currency.objects.create(name='Test Currency', symbol='T')
        self.currency2 = Currency.objects.create(name='Test Currency 2', symbol='T2')
        self.account1 = Account.objects.create(name='Test Account', currency=self.currency, user = self.user)
        self.account2 = Account.objects.create(name='Test Account 2', currency=self.currency, user = self.user)
        self.account3 = Account.objects.create(name='Test Account 3', currency=self.currency2, user = self.user)

        self.data = {
            'from_date': date(2023, 1, 1),
            'to_date': date(2023, 1, 31),
            'currency': self.currency.id,
        }
    
    def get_transaction_factory(self, **kwargs):
        return TransactionFactory(user=self.user, **kwargs)
    
    def get_currency_exchange_factory(self, **kwargs):
        return CurrencyExchangeFactory(user=self.user, **kwargs)

    def get_report_account_factory(self, **kwargs):
        return ReportAccountFactory(user=self.user, **kwargs)
    
    def test_api_create_report(self):
        TransactionFactory.create_batch(2, user = self.user, account=self.account1, date=datetime(2023, 1, 1, tzinfo=pytz.UTC), amount=75000)
        TransactionFactory.create_batch(2, user = self.user, account=self.account2, date=datetime(2023, 1, 1, tzinfo=pytz.UTC), amount=-25000)

        self.get_report_account_factory(
            from_date=date(2023, 1, 1),
            to_date=date(2023, 1, 31),
            account=self.account1,
        )
        self.get_report_account_factory(
            from_date=date(2023, 1, 1),
            to_date=date(2023, 1, 31),
            account=self.account2,
        )

        # not same currency and out of date range
        self.get_report_account_factory(
            from_date=date(2022, 1, 1),
            to_date=date(2022, 1, 31),
            account= self.account3,
        )
        self.get_transaction_factory(
            account=self.account3,
            date=datetime(2023, 1, 1, tzinfo=pytz.UTC),
            amount=75000
        )
        # same currency exchanges should be ignored
        ex1 = self.get_currency_exchange_factory(
            account=self.account2,
            amount=-7000,
            date=datetime(2023, 1, 1, tzinfo=pytz.UTC),
            type = 'from_same_currency',
        )
        ex2 = self.get_currency_exchange_factory(
            account=self.account1,
            related_transaction = ex1,
            amount=7000,
            date=datetime(2023, 1, 1, tzinfo=pytz.UTC),
            type='to_same_currency',
        )
        ex1.related_transaction = ex2
        ex1.save()

        # other currency exchange Transactions
        ex3 = self.get_currency_exchange_factory(
            account=self.account2,
            amount=7000,
            date=datetime(2023, 1, 1, tzinfo=pytz.UTC),
            type='from_different_currency',
        )
        ex4 = self.get_currency_exchange_factory(
            account=self.account3,
            related_transaction = ex3,
            amount=-7000,
            date=datetime(2023, 1, 1, tzinfo=pytz.UTC),
            type='to_different_currency',
        )
        ex3.related_transaction = ex4
        ex3.save()

        response = self.client.post(reverse('reports-currency-list'), self.data, format='json')
        db_report = ReportCurrency.objects.get()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ReportCurrency.objects.count(), 1)
        self.assertEqual(db_report.from_date, date(2023, 1, 1))
        self.assertEqual(db_report.to_date, date(2023, 1, 31))
        self.assertEqual(db_report.initial_balance, 400000)
        self.assertEqual(db_report.end_balance, 500000)
        self.assertEqual(db_report.total_income, 157000)
        self.assertEqual(db_report.total_expenses, -50000)
        self.assertEqual(db_report.currency.id, self.currency.id)

    def test_api_create_report_invalid_data(self):
        self.data['from_date'] = 'invalid'

        response = self.client.post(reverse('reports-currency-list'), self.data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ReportCurrency.objects.count(), 0)
    
    def test_api_create_report_invalid_currency(self):
        self.data['currency'] = 999

        response = self.client.post(reverse('reports-currency-list'), self.data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ReportCurrency.objects.count(), 0)

    def test_api_lists_reports(self):
        ReportCurrencyFactory(currency=self.currency, user = self.user)
        ReportCurrencyFactory(
            user = self.user,
            from_date=date(2020, 2, 1),
            to_date=date(2020, 2, 28),
            currency=self.currency
        )

        response = self.client.get(reverse('reports-currency-list'), format='json')
        json_data = response.json() 

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(json_data), 2)
        self.assertEqual(json_data[0]['from_date'], '2020-01-01')
        self.assertEqual(json_data[0]['to_date'], '2020-01-31')
        self.assertEqual(json_data[0]['initial_balance'], '2000.00')
        self.assertEqual(json_data[0]['end_balance'], '2500.00')
        self.assertEqual(json_data[0]['balance_status'], 'positive')
        self.assertEqual(json_data[0]['total_income'], '750.00')
        self.assertEqual(json_data[0]['total_expenses'], '-250.00')

    def test_api_lists_reports_by_currency(self):
        ReportCurrencyFactory(currency=self.currency, user = self.user)
        ReportCurrencyFactory(
            user = self.user,
            from_date=date(2020, 2, 1),
            to_date=date(2020, 2, 28),
            currency=self.currency
        )
        ReportCurrencyFactory(
            user = self.user,
            currency=self.currency2,
        )

        response = self.client.get(reverse('reports-currency-list'), { 'currency': self.currency.id }, format='json')
        json_data = response.json() 

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(json_data), 2)
        self.assertEqual(json_data[0]['from_date'], '2020-01-01')
        self.assertEqual(json_data[0]['to_date'], '2020-01-31')
        self.assertEqual(json_data[0]['initial_balance'], '2000.00')
        self.assertEqual(json_data[0]['end_balance'], '2500.00')
        self.assertEqual(json_data[0]['balance_status'], 'positive')
        self.assertEqual(json_data[0]['total_income'], '750.00')
        self.assertEqual(json_data[0]['total_expenses'], '-250.00')

    def test_api_lists_and_sorts_reports_by_from_date(self):
        AccountFactory(currency = self.currency, user = self.user)
        ReportCurrencyFactory(
            user = self.user,
            from_date=date(2023, 1, 1),
            to_date=date(2023, 1, 31),
            currency = self.currency,
        )
        ReportCurrencyFactory(
            user = self.user,
            from_date=date(2023, 2, 1),
            to_date=date(2023, 2, 28),
            currency = self.currency,
        )
        ReportCurrencyFactory(
            user = self.user,
            from_date=date(2023, 3, 1),
            to_date=date(2023, 3, 31),
            currency = self.currency,
        )

        response = self.client.get(reverse('reports-currency-list'), { 'ordering': '-from_date' }, format='json')
        json_data = response.json()

        self.assertEquals(len(json_data), 3)
        self.assertEquals(json_data[0]['from_date'], '2023-03-01')
        self.assertEquals(json_data[1]['from_date'], '2023-02-01')
        self.assertEquals(json_data[2]['from_date'], '2023-01-01')

    def test_api_get_report(self):
        AccountFactory(currency = self.currency, user = self.user)
        report = ReportCurrencyFactory(currency = self.currency, user = self.user)
        url = reverse('reports-currency-detail', kwargs={ 'pk': report.id })
        response = self.client.get(url, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        json_data = response.json() 
        self.assertEqual(json_data['from_date'], report.from_date)
        self.assertEqual(json_data['to_date'], report.to_date)
        self.assertEqual(json_data['initial_balance'], '2000.00')
        self.assertEqual(json_data['end_balance'], '2500.00')
        self.assertEqual(json_data['balance_status'], 'positive')
        self.assertEqual(json_data['total_income'], '750.00')
        self.assertEqual(json_data['total_expenses'], '-250.00')

    def test_api_updates_report(self):
        report = ReportCurrencyFactory(user = self.user)
        url = reverse('reports-currency-detail', kwargs={ 'pk': report.id })
        data = {
            'from_date': date(2023, 2, 1),
            'to_date': date(2023, 2, 28),
            'currency': self.currency.id,
        }

        response = self.client.put(url, data, format='json')
        json_data = response.json() 

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json_data['from_date'], '2023-02-01')
        self.assertEqual(json_data['to_date'], '2023-02-28')

    def test_api_updates_report_and_updates_calculations(self):
        ReportAccountFactory(
            user = self.user,
            from_date=date(2023, 1, 1),
            to_date=date(2023, 1, 31),
            account=self.account1,
        )
        ReportAccountFactory(
            user = self.user,
            from_date=date(2023, 1, 1),
            to_date=date(2023, 1, 31),
            account=self.account2,
        )
        report = ReportCurrencyFactory(currency=self.currency, user = self.user)
        TransactionFactory.create_batch(2, account=self.account1, date=datetime(2023, 1, 1, tzinfo=pytz.UTC), amount=75000, user = self.user)
        TransactionFactory.create_batch(2, account=self.account2, date=datetime(2023, 1, 1, tzinfo=pytz.UTC), amount=-25000, user = self.user)

        url = reverse('reports-currency-detail', kwargs={ 'pk': report.id })
        data = {
            'from_date': date(2023, 1, 1),
            'to_date': date(2023, 1, 30),
            'currency': self.currency.id,
        }
        response = self.client.put(url, data, format='json')
        json_data = response.json() 
        report = ReportCurrency.objects.get()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json_data['from_date'], '2023-01-01')
        self.assertEqual(json_data['to_date'], '2023-01-30')
        self.assertEqual(json_data['initial_balance'], '4000.00')
        self.assertEqual(json_data['end_balance'], '5000.00')
        self.assertEqual(json_data['balance_status'], 'positive')
        self.assertEqual(json_data['total_income'], '1500.00')
        self.assertEqual(json_data['total_expenses'], '-500.00')

        self.assertEqual(report.from_date, date(2023, 1, 1))
        self.assertEqual(report.to_date, date(2023, 1, 30))
        self.assertEqual(report.initial_balance, 400000)
        self.assertEqual(report.end_balance, 500000)
        self.assertEqual(report.total_income, 150000)
        self.assertEqual(report.total_expenses, -50000)
        self.assertEqual(report.currency.id, self.currency.id)
    
    def test_api_deletes_report(self):
        report = ReportCurrencyFactory(user = self.user)

        url = reverse('reports-currency-detail', kwargs={ 'pk': report.id })
        response = self.client.delete(url, format='json')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(ReportCurrency.objects.count(), 0)

