import factory
from factory.django import DjangoModelFactory

from japb_api.transactions.models import Transaction, CurrencyExchange, Category
from japb_api.accounts.factories import AccountFactory
from japb_api.users.factories import UserFactory


class TransactionFactory(DjangoModelFactory):
    class Meta:
        model = Transaction
    
    user = factory.SubFactory(UserFactory)
    amount = factory.Faker('random_int', min=-2000, max=2000)
    description = 'transaction 1'
    account = factory.SubFactory(AccountFactory)
    category = None
    date = '2020-01-01T00:00:00Z'
    created_at = '2020-01-01T00:00:00Z'
    updated_at = '2020-01-01T00:00:00Z'

class CurrencyExchangeFactory(DjangoModelFactory):
    class Meta:
        model = CurrencyExchange
    
    user = factory.SubFactory(UserFactory)
    description = 'currency exchange 1'
    amount = 1000
    account = factory.SubFactory(AccountFactory)
    related_transaction = None
    date = '2020-01-01T00:00:00Z'
    created_at = '2020-01-01T00:00:00Z'
    updated_at = '2020-01-01T00:00:00Z'

class ExchangeComissionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'transactions.ExchangeComission'

    id = factory.Sequence(lambda n: f'{n}')
    user = factory.SubFactory(UserFactory)
    amount = 1000
    account = factory.Sequence(lambda n: f'{n}')
    date = factory.Faker('date_time')
    type = 'comission'
    exchange_from = factory.Sequence(lambda n: f'{n}')
    exchange_to = factory.Sequence(lambda n: f'{n}')
    created_at = factory.Faker('date_time')
    updated_at = factory.Faker('date_time')
   
class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category
    
    user = factory.SubFactory(UserFactory)
    name = 'test category'
    description = 'test category description'
    color = '#ffffff'
    parent_category = None
    created_at = '2020-01-01T00:00:00Z'
    updated_at = '2020-01-01T00:00:00Z'
