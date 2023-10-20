import pytz
from datetime import datetime
from django.test import TestCase
from japb_api.currencies.models import Currency
from japb_api.accounts.models import Account
from japb_api.transactions.models import Transaction
from japb_api.reports.models import Report

class TestReportModel(TestCase):
    def setUp(self):
        self.currency = Currency.objects.create(name='Test Currency', symbol='T')
        self.account = Account.objects.create(name='Test Account', currency=self.currency)
        self.transactions = [
            Transaction(
                amount= 6000,
                description="transaction 0",
                account=self.account,
                date=datetime(2022, 12, 1, tzinfo=pytz.UTC)
            ),
            Transaction(
                amount= 1064,
                description="transaction 1",
                account=self.account,
                date=datetime(2022, 12, 2, tzinfo=pytz.UTC)
            ),
            Transaction(
                amount= 50,
                description="transaction 2",
                account=self.account,
                date=datetime(2022, 12, 3, tzinfo=pytz.UTC)
            ),
            Transaction(
                amount= 50,
                description="transaction 3",
                account=self.account,
                date=datetime(2022, 12, 4, tzinfo=pytz.UTC)
            ),
            Transaction(
                amount= -50,
                description="transaction 4",
                account=self.account,
                date=datetime(2022, 12, 4, tzinfo=pytz.UTC)
            ),
        ]

    def test_can_calculate_initial_balance(self):
        Transaction.objects.bulk_create(self.transactions)
        data = {
            'from_date': datetime(2022, 12, 2, tzinfo=pytz.UTC),
            'to_date': datetime(2022, 12, 4, tzinfo=pytz.UTC),
            'account': self.account,
        }
        report = Report.objects.create(**data)

        report.calculate_initial_balance()

        self.assertEquals(report.initial_balance, 6000)

    def test_can_calculate_final_balance(self):
        Transaction.objects.bulk_create(self.transactions)
        data = {
            'from_date': datetime(2022, 12, 2, tzinfo=pytz.UTC),
            'to_date': datetime(2022, 12, 4, tzinfo=pytz.UTC),
            'account': self.account,
        }
        report = Report.objects.create(**data)
        report.calculate_end_balance()
        self.assertEquals(report.end_balance, 7114)
    
    def test_can_calculate_total_income(self):
        Transaction.objects.bulk_create(self.transactions)
        data = {
            'from_date': datetime(2022, 12, 2, tzinfo=pytz.UTC),
            'to_date': datetime(2022, 12, 4, tzinfo=pytz.UTC),
            'account': self.account,
        }
        report = Report.objects.create(**data)
        report.calculate_total_income()
        self.assertEquals(report.total_income, 1164)

    def test_can_calculate_total_expenses(self):
        Transaction.objects.bulk_create(self.transactions)
        data = {
            'from_date': datetime(2022, 12, 2, tzinfo=pytz.UTC),
            'to_date': datetime(2022, 12, 4, tzinfo=pytz.UTC),
            'account': self.account,
        }
        report = Report.objects.create(**data)
        report.calculate_total_expenses()
        self.assertEquals(report.total_expenses, -50)
    
    def test_can_calculate_all_fields(self):
        Transaction.objects.bulk_create(self.transactions)
        data = {
            'from_date': datetime(2022, 12, 2, tzinfo=pytz.UTC),
            'to_date': datetime(2022, 12, 4, tzinfo=pytz.UTC),
            'account': self.account,
        }
        report = Report.objects.create(**data)
        report.calculate_initial_balance()
        report.calculate_end_balance()
        report.calculate_total_income()
        report.calculate_total_expenses()

        self.assertEquals(report.initial_balance, 6000)
        self.assertEquals(report.end_balance, 7114)
        self.assertEquals(report.total_income, 1164)
        self.assertEquals(report.total_expenses, -50)
