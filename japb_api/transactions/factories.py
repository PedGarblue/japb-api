import factory
from factory.django import DjangoModelFactory

from japb_api.transactions.models import Transaction, CurrencyExchange
from japb_api.accounts.factories import AccountFactory


class TransactionFactory(DjangoModelFactory):
    class Meta:
        model = Transaction
    
    description = 'transaction 1'
    amount = 1000
    account = factory.SubFactory(AccountFactory)
    date = '2020-01-01T00:00:00Z'
    created_at = '2020-01-01T00:00:00Z'
    updated_at = '2020-01-01T00:00:00Z'

class CurrencyExchangeFactory(DjangoModelFactory):
    class Meta:
        model = CurrencyExchange
    
    description = 'currency exchange 1'
    amount = 1000
    account = factory.SubFactory(AccountFactory)
    related_transaction = None
    date = '2020-01-01T00:00:00Z'
    created_at = '2020-01-01T00:00:00Z'
    updated_at = '2020-01-01T00:00:00Z'
   