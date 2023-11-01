import faker
from factory.django import DjangoModelFactory

from japb_api.currencies.models import Currency


class CurrencyFactory(DjangoModelFactory):
    class Meta:
        model = Currency
    name = 'Euro'
    symbol = '€'
