from typing import Any
from django.test import TestCase

from japb_api.currencies.factory import CurrencyFactory
from japb_api.accounts.factory import AccountFactory
from japb_api.transactions.models import Transaction, CurrencyExchange
from japb_api.transactions.factories import TransactionFactory, CurrencyExchangeFactory

class TestTransactionModel(TestCase):
    def setUp(self) -> None:
        self.currency = CurrencyFactory()
        self.currency2 = CurrencyFactory()
        self.account = AccountFactory(currency = self.currency)
        self.account2 = AccountFactory(currency = self.currency)

    def test_transaction_str(self) -> None:
        transaction = TransactionFactory(description = 'test transaction', account = self.account, amount = 1000)
        self.assertEqual(str(transaction), 'test transaction 1000')

class TestCurrencyExchangeModel(TestCase):

    def setUp(self):
        self.currency = CurrencyFactory()
        self.currency2 = CurrencyFactory()
        self.account = AccountFactory(currency = self.currency)
        self.account2 = AccountFactory(currency = self.currency)
