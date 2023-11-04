from datetime import datetime
from django.utils import timezone
from django.db import models
from django.db.models.query import QuerySet
from japb_api.currencies.models import Currency
from japb_api.accounts.models import Account
from japb_api.transactions.models import Transaction, CurrencyExchange

class Report(models.Model):
    from_date = models.DateField()
    to_date = models.DateField()
    # balances are stored as integers just like transactions
    initial_balance = models.IntegerField(default=0)
    end_balance = models.IntegerField(default=0)
    total_income = models.IntegerField(default=0)
    total_expenses = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def get_from_date(self) -> datetime:
        return datetime(year=self.from_date.year, month=self.from_date.month, day=self.from_date.day, hour=0, minute=0, second=0, microsecond=0)

    def get_to_date(self) -> datetime:
        return datetime(year=self.to_date.year, month=self.to_date.month, day=self.to_date.day, hour=23, minute=59, second=59, microsecond=999999)
        
    def get_from_date_with_timezone(self) -> datetime:
        return timezone.make_aware(self.get_from_date())

    def get_to_date_with_timezone(self) -> datetime:
        return timezone.make_aware(self.get_to_date())

class ReportAccount(Report):
    account = models.ForeignKey(Account, on_delete=models.CASCADE)

    def calculate_initial_balance(self) -> 'ReportAccount':
        transactions = Transaction.objects.filter(account=self.account, date__lt=self.get_from_date_with_timezone())
        transactions_sum = transactions.aggregate(models.Sum('amount'))['amount__sum']
        self.initial_balance = transactions_sum if transactions_sum else 0
        return self

    def calculate_end_balance(self) -> 'ReportAccount':
        transactions = Transaction.objects.filter(account=self.account, date__lte=self.get_to_date_with_timezone())
        transactions_sum = transactions.aggregate(models.Sum('amount'))['amount__sum']
        self.end_balance = transactions_sum if transactions_sum else 0
        return self

    def calculate_total_income(self) -> 'ReportAccount':
        transactions = Transaction.objects.filter(account=self.account, date__range=[self.get_from_date_with_timezone(), self.get_to_date_with_timezone()], amount__gt=0)
        transactions_sum = transactions.aggregate(models.Sum('amount'))['amount__sum']
        self.total_income = transactions_sum if transactions_sum else 0
        return self
    
    def calculate_total_expenses(self) -> 'ReportAccount':
        transactions = Transaction.objects.filter(account=self.account, date__range=[self.get_from_date_with_timezone(), self.get_to_date_with_timezone()], amount__lt=0)
        transactions_sum = transactions.aggregate(models.Sum('amount'))['amount__sum']
        self.total_expenses = transactions_sum if transactions_sum else 0
        return self

class ReportCurrency(Report):
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE)

    def get_account_reports_in_month_range(self) -> QuerySet['ReportAccount']:
        return ReportAccount.objects.filter(
            account__currency=self.currency,
            from_date__range=[self.get_from_date_with_timezone(), self.get_to_date_with_timezone()]
        )
    
    def get_transactions_in_month_range(self) -> QuerySet['Transaction']:
        return Transaction.objects.filter(
            account__currency=self.currency,
            date__range=[self.get_from_date_with_timezone(), self.get_to_date_with_timezone()]
        )
    
    def get_exchanges_in_month_range(self) -> QuerySet['CurrencyExchange']:
        return CurrencyExchange.objects.filter(
            account__currency=self.currency,
            date__range=[self.get_from_date_with_timezone(), self.get_to_date_with_timezone()]
        )

    def calculate_initial_balance(self) -> 'ReportCurrency':
        reports = self.get_account_reports_in_month_range()
        reports_sum = reports.aggregate(models.Sum('initial_balance'))['initial_balance__sum']
        self.initial_balance = reports_sum if reports_sum else 0
        return self

    def calculate_end_balance(self) -> 'ReportCurrency':
        reports = self.get_account_reports_in_month_range()
        reports_sum = reports.aggregate(models.Sum('end_balance'))['end_balance__sum']
        self.end_balance = reports_sum if reports_sum else 0
        return self

    def calculate_total_income(self) -> 'ReportCurrency':
        exchanges_income_from_same_currency = self.get_exchanges_in_month_range()\
            .filter(
                related_transaction__account__currency=self.currency,
                amount__gt=0,
            )
        transactions = self.get_transactions_in_month_range()\
            .filter(
                amount__gt=0
            )\
            .exclude(id__in=exchanges_income_from_same_currency)
        transactions_sum = transactions.aggregate(models.Sum('amount'))['amount__sum']
        self.total_income = transactions_sum if transactions_sum else 0
        return self
    
    def calculate_total_expenses(self) -> 'ReportCurrency':
        exchanges_expense_from_same_currency = self.get_exchanges_in_month_range()\
            .filter(
                related_transaction__account__currency=self.currency,
                amount__lt=0,
            )

        transactions = self.get_transactions_in_month_range()\
            .filter(
                amount__lt=0
            )\
            .exclude(id__in=exchanges_expense_from_same_currency)
        transactions_sum = transactions.aggregate(models.Sum('amount'))['amount__sum']

        self.total_expenses = transactions_sum if transactions_sum else 0
        return self
