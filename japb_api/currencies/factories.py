import faker
from factory.django import DjangoModelFactory
from factory import SubFactory

from japb_api.currencies.models import Currency, CurrencyConversionHistorial


class CurrencyFactory(DjangoModelFactory):
    class Meta:
        model = Currency
    name = 'Euro'
    symbol = '€'

class CurrencyConversionHistorialFactory(DjangoModelFactory):
    class Meta:
        model = CurrencyConversionHistorial
    
    user = None  # Can be None as per model definition
    currency_from = SubFactory(CurrencyFactory)
    currency_to = SubFactory(CurrencyFactory)
    rate = 1.0  # Default conversion rate
    date = faker.Faker().date_time()

    