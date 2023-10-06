from factory.django import DjangoModelFactory
from ..models import Currency

class CurrencyFactory (DjangoModelFactory):
    class Meta:
        model = Currency
    name = 'USD'
    symbol = '$'
    decimal_places = 2

