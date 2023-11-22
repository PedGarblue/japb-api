import factory


class TransactionFactory(factory.django.DjangoModelFactory):

    class Meta:
        model = 'transactions.Transaction'
        # django_get_or_create = ('',)

    id = factory.Sequence(lambda n: f'{n}')
    amount = factory.Faker('pydecimal', right_digits=2)
    account = factory.Sequence(lambda n: f'{n}')
    date = factory.Faker('date_time')
    created_at = factory.Faker('date_time')
    updated_at = factory.Faker('date_time')

class CurrencyExchangeFactory(factory.django.DjangoModelFactory):

    class Meta:
        model = 'transactions.CurrencyExchange'
        # django_get_or_create = ('',)

    id = factory.Sequence(lambda n: f'{n}')
    amount = factory.Faker('pydecimal', right_digits=2)
    account = factory.Sequence(lambda n: f'{n}')
    date = factory.Faker('date_time')
    created_at = factory.Faker('date_time')
    updated_at = factory.Faker('date_time')
    related_transaction = factory.Sequence(lambda n: f'{n}')

class CategoryFactory(factory.django.DjangoModelFactory):

    class Meta:
        model = 'transactions.Category'
        # django_get_or_create = ('',)

    id = factory.Sequence(lambda n: f'{n}')
    name = factory.Faker('name')
    parent_category = factory.Sequence(lambda n: f'{n}')
    color = factory.Faker('color')
    type = 'expense'
    created_at = factory.Faker('date_time')
    updated_at = factory.Faker('date_time')