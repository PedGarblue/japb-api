from factory.django import DjangoModelFactory
from factory import SubFactory, Faker

from japb_api.currencies.models import Currency, CurrencyConversionHistorial


class CurrencyFactory(DjangoModelFactory):
    class Meta:
        model = Currency

    name = Faker(
        "currency_code"
    )  # Generates random currency codes like 'USD', 'EUR', etc.
    symbol = Faker("currency_symbol")


class CurrencyConversionHistorialFactory(DjangoModelFactory):
    class Meta:
        model = CurrencyConversionHistorial

    user = None  # Can be None as per model definition
    currency_from = SubFactory(CurrencyFactory)
    currency_to = SubFactory(CurrencyFactory)
    rate = 1.0  # Default conversion rate
    date = Faker("date_time")
