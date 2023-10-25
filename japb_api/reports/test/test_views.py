import pytz
from datetime import date
from datetime import datetime
from faker import Faker
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Report
from japb_api.accounts.models import Account
from japb_api.currencies.models import Currency
from japb_api.transactions.models import Transaction

class TestReportViews(APITestCase):
    def setUp(self):
        self.fake = Faker(['en-US'])
        self.currency = Currency.objects.create(name='Test Currency', symbol='T')
        self.account = Account.objects.create(name='Test Account', currency=self.currency)
        self.data = {
            'from_date': date(2023, 1, 1),
            'to_date': date(2023, 1, 31),
            'account': self.account.id,
        }
        self.transactions = [
            # initial balance transaction
            Transaction(
                amount= 6000,
                description="transaction initial balance",
                account=self.account,
                date=datetime(2022, 12, 30, tzinfo=pytz.UTC)
            ),
            # income transactions
            Transaction(
                amount=1064,
                description="transaction income 1",
                account=self.account,
                date=datetime(2023, 1, 1, tzinfo=pytz.UTC)
            ),
            Transaction(
                amount=3046,
                description="transaction income 2",
                account=self.account,
                date=datetime(2023,1, 3, tzinfo=pytz.UTC)
            ),
            # expense transactions
            Transaction(
                amount=-4100,
                description="transaction expense 3",
                account=self.account,
                date=datetime(2023, 1, 4, tzinfo=pytz.UTC)
            )
        ]
    
    def test_api_create_report(self):
        response = self.client.post(reverse('reports-list'), self.data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Report.objects.count(), 1)
        db_report = Report.objects.get()
        self.assertEqual(db_report.from_date, date(2023, 1, 1))
        self.assertEqual(db_report.to_date, date(2023, 1, 31))
        self.assertEqual(db_report.initial_balance, 0)
        self.assertEqual(db_report.end_balance, 0)
        self.assertEqual(db_report.total_income, 0)
        self.assertEqual(db_report.total_expenses, 0)
        self.assertEqual(db_report.account.id, self.account.id)

    def test_api_create_report_invalid_data(self):
        self.data['from_date'] = 'invalid'
        response = self.client.post(reverse('reports-list'), self.data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Report.objects.count(), 0)
    
    def test_api_create_report_invalid_account(self):
        self.data['account'] = 999
        response = self.client.post(reverse('reports-list'), self.data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Report.objects.count(), 0)
    
    def test_api_create_report_calculates_balances_income_and_expences(self):
        Transaction.objects.bulk_create(self.transactions) 
        
        self.client.post(reverse('reports-list'), self.data, format='json')
        self.assertEqual(Report.objects.count(), 1)
        db_report = Report.objects.get()

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
        account2 = Account.objects.create(name='Test Account 2', currency=self.currency)
        Report.objects.create(
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

    def test_api_get_report(self):
        Transaction.objects.bulk_create(self.transactions) 
        self.client.post(reverse('reports-list'), self.data, format='json')
        report = Report.objects.get()

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
        report = Report.objects.get()

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
        report = Report.objects.get()

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
        report = Report.objects.get()

        url = reverse('reports-detail', kwargs={ 'pk': report.id })
        response = self.client.delete(url, format='json')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Report.objects.count(), 0)
