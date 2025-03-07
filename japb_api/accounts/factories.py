import factory
from factory.django import DjangoModelFactory

from japb_api.accounts.models import Account
from japb_api.currencies.factories import CurrencyFactory


class AccountFactory(DjangoModelFactory):
    class Meta:
        model = Account

    user = factory.SubFactory("japb_api.users.factories.UserFactory")
    name = "Account 1"
    currency = factory.SubFactory(CurrencyFactory)
    decimal_places = 2
    created_at = "2020-01-01T00:00:00Z"
    updated_at = "2020-01-01T00:00:00Z"
