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
