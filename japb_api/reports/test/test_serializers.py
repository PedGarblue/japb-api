from django.test import TestCase
from japb_api.currencies.models import Currency
from japb_api.accounts.models import Account
from japb_api.reports.models import ReportAccount, ReportCurrency
from japb_api.reports.serializers import ReportAccountSerializer, ReportCurrencySerializer


class ReportSerializerTestCase(TestCase):

    def setUp(self):
        self.currency = Currency.objects.create(
            name='Test Currency',
            symbol='$',
        )
        self.account = Account.objects.create(
            name='Test Account',
            currency=self.currency,
        )
        self.report = ReportAccount.objects.create(
            from_date='2020-01-01',
            to_date='2020-01-31',
            initial_balance=200000,
            end_balance=250000,
            total_income=75000,
            total_expenses=25000,
            account=self.account,
        )
        self.serializer = ReportAccountSerializer(instance=self.report)

    def test_contains_expected_fields(self):
        data = self.serializer.data
        self.assertCountEqual(data.keys(), [
            'id',
            'from_date',
            'to_date',
            'initial_balance',
            'end_balance',
            'balance_status',
            'total_income',
            'total_expenses',
            'account',
            'created_at',
            'updated_at',
        ])

    def test_formats_amount_fields(self):
        data = self.serializer.data
        self.assertEqual(data['initial_balance'], '2000.00')
        self.assertEqual(data['end_balance'], '2500.00')
        self.assertEqual(data['total_income'], '750.00')
        self.assertEqual(data['total_expenses'], '250.00')

    def test_contains_method_field_balance_status_positive(self):
        data = self.serializer.data
        self.assertEqual(data['balance_status'], 'positive')

    def test_contains_method_field_balance_status_negative(self):
        self.report.end_balance = 150000
        data = self.serializer.data
        self.assertEqual(data['balance_status'], 'negative')

    def test_contains_method_field_balance_status_neutral(self):
        self.report.end_balance = 200000
        data = self.serializer.data
        self.assertEqual(data['balance_status'], 'neutral')
    

class CurrencyReportSerializerTestCase(TestCase):
    
        def setUp(self):
            self.currency = Currency.objects.create(
                name='Test Currency',
                symbol='$',
            )
            self.account = Account.objects.create(
                name='Test Account',
                currency=self.currency,
            )
            self.report = ReportCurrency.objects.create(
                from_date='2020-01-01',
                to_date='2020-01-31',
                initial_balance=200000,
                end_balance=250000,
                total_income=75000,
                total_expenses=25000,
                currency=self.currency,
            )
            self.serializer = ReportCurrencySerializer(instance=self.report)
    
        def test_contains_expected_fields(self):
            data = self.serializer.data
            self.assertCountEqual(data.keys(), [
                'id',
                'from_date',
                'to_date',
                'initial_balance',
                'end_balance',
                'balance_status',
                'total_income',
                'total_expenses',
                'currency',
                'created_at',
                'updated_at',
            ])
    
        def test_formats_amount_fields(self):
            data = self.serializer.data
            self.assertEqual(data['initial_balance'], '2000.00')
            self.assertEqual(data['end_balance'], '2500.00')
            self.assertEqual(data['total_income'], '750.00')
            self.assertEqual(data['total_expenses'], '250.00')
    
        def test_contains_method_field_balance_status_positive(self):
            data = self.serializer.data
            self.assertEqual(data['balance_status'], 'positive')
    
        def test_contains_method_field_balance_status_negative(self):
            self.report.end_balance = 150000
            data = self.serializer.data
            self.assertEqual(data['balance_status'], 'negative')
    
        def test_contains_method_field_balance_status_neutral(self):
            self.report.end_balance = 200000
            data = self.serializer.data
            self.assertEqual(data['balance_status'], 'neutral')