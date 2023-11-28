import pytz
from datetime import datetime, timezone
from django.test import TestCase

from japb_api.currencies.factories import CurrencyFactory
from japb_api.accounts.factories import AccountFactory
from japb_api.transactions.models import Transaction, CurrencyExchange, Category
from japb_api.transactions.factories import TransactionFactory, CategoryFactory

class TestTransactionModel(TestCase):
    def setUp(self) -> None:
        self.currency = CurrencyFactory()
        self.currency2 = CurrencyFactory()
        self.account = AccountFactory(currency = self.currency)
        self.account2 = AccountFactory(currency = self.currency)
        self.category = CategoryFactory()

    def test_transaction_str(self) -> None:
        transaction = TransactionFactory(description = 'test transaction', account = self.account, amount = 1000, category = self.category)
        self.assertEqual(str(transaction), 'test transaction 1000')
    
    def test_transaction_fields(self) -> None:
        transaction = TransactionFactory(description = 'test transaction', account = self.account, amount = 1000, category = self.category)
        self.assertEqual(transaction.description, 'test transaction')
        self.assertEqual(transaction.account, self.account)
        self.assertEquals(transaction.category, self.category)
        self.assertEqual(transaction.amount, 1000)

    def test_transaction_with_category(self) -> None:
        transaction = TransactionFactory(description = 'test transaction', account = self.account, amount = 1000, category = self.category)
        self.assertEqual(transaction.category, self.category)

class TestCurrencyExchangeModel(TestCase):

    def setUp(self):
        self.currency = CurrencyFactory()
        self.currency2 = CurrencyFactory()
        self.account = AccountFactory(currency = self.currency)
        self.account2 = AccountFactory(currency = self.currency)
    
    def test_currency_exchange_fields(self) -> None:
        currency_exchange = CurrencyExchange.objects.create(
            description = 'test currency exchange',
            date = datetime.now(tz=timezone.utc),
            account = self.account,
            amount = 1000,
            type='from_same_currency',
            category = None,
        )
        self.assertEqual(currency_exchange.description, 'test currency exchange')
        self.assertEqual(currency_exchange.account, self.account)
        self.assertEqual(currency_exchange.amount, 1000)
        self.assertEqual(currency_exchange.type, 'from_same_currency')
    

class TestTransactionCategoryModel(TestCase):
    def setUp(self) -> None:
        self.currency = CurrencyFactory()
        self.currency2 = CurrencyFactory()
        self.account = AccountFactory(currency = self.currency)
        self.account2 = AccountFactory(currency = self.currency)

    def test_category_fields(self) -> None:
        category = CategoryFactory(name = 'test category')
        self.assertEqual(category.name, 'test category')
        self.assertEqual(category.description, 'test category description')
        self.assertEqual(category.color, '#ffffff')
        self.assertEqual(category.type, 'expense')
    
    def test_category_with_parent_category(self) -> None:
        parent_category = CategoryFactory(name = 'test parent category')
        category = CategoryFactory(name = 'test category', parent_category = parent_category)
        self.assertEqual(category.parent_category, parent_category)
