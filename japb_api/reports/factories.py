import factory
from factory.django import DjangoModelFactory

from japb_api.reports.models import ReportAccount, ReportCurrency
from japb_api.currencies.factories import CurrencyFactory
from japb_api.accounts.factories import AccountFactory


class ReportAccountFactory(DjangoModelFactory):
    class Meta:
        model = ReportAccount
   
    from_date = '2020-01-01' 
    to_date = '2020-01-31'
    initial_balance = 200000
    end_balance = 250000
    total_income = 75000
    total_expenses = -25000
    account = factory.SubFactory(AccountFactory)
    created_at = '2020-01-01T00:00:00Z'
    updated_at = '2020-01-01T00:00:00Z'

class ReportCurrencyFactory(DjangoModelFactory):
    class Meta:
        model = ReportCurrency

    from_date = '2020-01-01'
    to_date = '2020-01-31'
    initial_balance = 200000
    end_balance = 250000
    total_income = 75000
    total_expenses = -25000
    currency = factory.SubFactory(CurrencyFactory)
    created_at = '2020-01-01T00:00:00Z'
    updated_at = '2020-01-01T00:00:00Z'

