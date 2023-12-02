import pytz
from datetime import datetime
from datetime import date
from django.test import TestCase
from japb_api.currencies.models import Currency
from japb_api.accounts.models import Account
from japb_api.transactions.models import Transaction
from japb_api.transactions.factories import TransactionFactory, CurrencyExchangeFactory
from japb_api.reports.models import ReportAccount, ReportCurrency
from japb_api.reports.factories import ReportAccountFactory

class TestReportAccountModel(TestCase):
    def setUp(self):
        self.currency = Currency.objects.create(name='Test Currency', symbol='T')
        self.currency2 = Currency.objects.create(name='Test Currency', symbol='T')
        self.account = Account.objects.create(name='Test Account', currency=self.currency)
        self.account2 = Account.objects.create(name='Test Account 2', currency=self.currency)
        self.account3 = Account.objects.create(name='Test Account 2', currency=self.currency2)
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
        report = ReportAccount.objects.create(**data)

        report.calculate_initial_balance()

        self.assertEquals(report.initial_balance, 6000)

    def test_can_calculate_final_balance(self):
        Transaction.objects.bulk_create(self.transactions)
        data = {
            'from_date': datetime(2022, 12, 2, tzinfo=pytz.UTC),
            'to_date': datetime(2022, 12, 4, tzinfo=pytz.UTC),
            'account': self.account,
        }
        report = ReportAccount.objects.create(**data)
        report.calculate_end_balance()
        self.assertEquals(report.end_balance, 7114)
    
    def test_can_calculate_total_income(self):
        Transaction.objects.bulk_create(self.transactions)
        data = {
            'from_date': datetime(2022, 12, 2, tzinfo=pytz.UTC),
            'to_date': datetime(2022, 12, 4, tzinfo=pytz.UTC),
            'account': self.account,
        }
        report = ReportAccount.objects.create(**data)
        report.calculate_total_income()
        self.assertEquals(report.total_income, 1164)

    def test_can_calculate_total_expenses(self):
        Transaction.objects.bulk_create(self.transactions)
        data = {
            'from_date': datetime(2022, 12, 2, tzinfo=pytz.UTC),
            'to_date': datetime(2022, 12, 4, tzinfo=pytz.UTC),
            'account': self.account,
        }
        report = ReportAccount.objects.create(**data)
        report.calculate_total_expenses()
        self.assertEquals(report.total_expenses, -50)
    
    def test_can_calculate_all_fields(self):
        Transaction.objects.bulk_create(self.transactions)
        data = {
            'from_date': datetime(2022, 12, 2, tzinfo=pytz.UTC),
            'to_date': datetime(2022, 12, 4, tzinfo=pytz.UTC),
            'account': self.account,
        }
        report = ReportAccount.objects.create(**data)
        report.calculate_initial_balance()
        report.calculate_end_balance()
        report.calculate_total_income()
        report.calculate_total_expenses()

        self.assertEquals(report.initial_balance, 6000)
        self.assertEquals(report.end_balance, 7114)
        self.assertEquals(report.total_income, 1164)
        self.assertEquals(report.total_expenses, -50)

class TestReportCurrencyModel(TestCase):
    def setUp(self):
        self.currency = Currency.objects.create(name='Test Currency', symbol='T')
        self.currency2 = Currency.objects.create(name='Test Currency 2', symbol='T2')
        self.account1 = Account.objects.create(name='Test Account 1', currency=self.currency)
        self.account2 = Account.objects.create(name='Test Account 2', currency=self.currency)
        self.account3 = Account.objects.create(name='Test Account 3', currency=self.currency2)
        self.data = {
            'from_date': date(2020, 1, 1),
            'to_date': date(2020, 1, 31),
            'currency': self.currency,
        }

    def test_can_calculate_initial_balance(self):
        ReportAccountFactory(initial_balance=200000, account=self.account1) 
        ReportAccountFactory(initial_balance=200000, account=self.account2) 
        # Not same currency
        ReportAccountFactory(
            account=self.account3
        )
        # Not in range
        ReportAccountFactory(
            from_date='2019-12-01',
            to_date='2019-12-31',
            initial_balance=30000,
            account=self.account1
        )
        # Not in range
        ReportAccountFactory(
            from_date='2021-12-01',
            to_date='2021-12-31',
            initial_balance=30000,
            account=self.account2
        )

        report = ReportCurrency.objects.create(**self.data)
        report.calculate_initial_balance()

        self.assertEquals(report.initial_balance, 400000)

    def test_can_calculate_final_balance(self):
        ReportAccountFactory(end_balance=400000, account=self.account1) 
        ReportAccountFactory(end_balance=200000, account=self.account2) 
        # Not same currency
        ReportAccountFactory(
            account=self.account3
        )
        # Not in range
        ReportAccountFactory(
            from_date='2019-12-01',
            to_date='2019-12-31',
            end_balance=30000,
            account=self.account1
        )
        # Not in range
        ReportAccountFactory(
            from_date='2021-12-01',
            to_date='2021-12-31',
            end_balance=30000,
            account=self.account2
        )

        report = ReportCurrency.objects.create(**self.data)
        report.calculate_end_balance()

        self.assertEquals(report.end_balance, 600000)
    
    def test_can_calculate_total_income(self):
        TransactionFactory.create_batch(2, amount=1000, account=self.account1, date=datetime(2020, 1, 1, tzinfo=pytz.UTC))
        TransactionFactory.create_batch(2, amount=1000, account=self.account2, date=datetime(2020, 1, 31, tzinfo=pytz.UTC))
        # Not same currency
        TransactionFactory(
            account=self.account3
        )
        # Not in range
        TransactionFactory(
            date=datetime(2019, 12, 1, tzinfo=pytz.UTC),
        )
        # Not in range
        TransactionFactory(
            date=datetime(2020, 2, 1, tzinfo=pytz.UTC),
        )
        # same currency exchange Transactions
        ex1 = CurrencyExchangeFactory(account=self.account1, amount=-2000, date=datetime(2020, 1, 1, tzinfo=pytz.UTC), type = 'from_same_currency')
        ex2 = CurrencyExchangeFactory(account=self.account2, related_transaction = ex1, amount=2000, date=datetime(2020, 1, 1, tzinfo=pytz.UTC), type = 'to_same_currency')
        ex1.related_transaction = ex2
        ex1.save()

        # other currency exchange Transactions
        ex3 = CurrencyExchangeFactory(account=self.account3, amount=-2000, type = 'from_different_currency', date=datetime(2020, 1, 1, tzinfo=pytz.UTC))
        ex4 = CurrencyExchangeFactory(account=self.account1, related_transaction = ex3, amount=2000, type = 'to_different_currency', date=datetime(2020, 1, 1, tzinfo=pytz.UTC))
        ex3.related_transaction = ex4
        ex3.save()

        report = ReportCurrency.objects.create(**self.data)
        report.calculate_total_income()

        self.assertEqual(report.total_income, 6000)

    def test_can_calculate_total_expenses(self):
        # must be 160
        TransactionFactory.create_batch(2, amount=-40, account=self.account1, date=datetime(2020, 1, 1, tzinfo=pytz.UTC))
        TransactionFactory.create_batch(2, amount=-40, account=self.account2, date=datetime(2020, 1, 31, tzinfo=pytz.UTC))

        # Not same currency
        TransactionFactory(account=self.account3, amount=-37.5)
        # Not in range
        TransactionFactory(
            date=datetime(2019, 12, 1, tzinfo=pytz.UTC),
            amount=-37.5
        )
        # Not in range
        TransactionFactory(
            date=datetime(2020, 2, 1, tzinfo=pytz.UTC),
            amount=-37.5
        )
        # same currency exchange Transactions should not be counted
        ex1 = CurrencyExchangeFactory(amount=-75, account=self.account1, date=datetime(2020, 1, 2, tzinfo=pytz.UTC), type='from_same_currency')
        ex2 = CurrencyExchangeFactory(related_transaction = ex1, amount=75, account = self.account2, date=datetime(2020, 1, 2, tzinfo=pytz.UTC), type='to_same_currency')
        ex1.related_transaction = ex2
        ex1.save()

        report = ReportCurrency.objects.create(**self.data)
        report.calculate_total_expenses()

        self.assertEquals(report.total_expenses, -160)
    
    def test_can_calculate_all_fields(self):
        ReportAccountFactory(initial_balance=6000, end_balance=7114, total_income=1164, total_expenses=-50, account=self.account1)
        ReportAccountFactory(initial_balance=6000, end_balance=7114, total_income=1164, total_expenses=-50, account=self.account2)
        TransactionFactory(amount=1164, account=self.account1, date=datetime(2020, 1, 1, tzinfo=pytz.UTC))
        TransactionFactory(amount=1164, account=self.account2, date=datetime(2020, 1, 1, tzinfo=pytz.UTC))
        TransactionFactory(amount=-50, account=self.account1, date=datetime(2020, 1, 1, tzinfo=pytz.UTC))
        TransactionFactory(amount=-50, account=self.account2, date=datetime(2020, 1, 1, tzinfo=pytz.UTC))

        report = ReportCurrency.objects.create(**self.data)

        report.calculate_initial_balance()
        report.calculate_end_balance()
        report.calculate_total_income()
        report.calculate_total_expenses()

        self.assertEquals(report.initial_balance, 12000)
        self.assertEquals(report.end_balance, 14228)
        self.assertEquals(report.total_income, 2328)
        self.assertEquals(report.total_expenses, -100)
