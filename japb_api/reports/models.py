from datetime import datetime
from django.utils import timezone
from django.db import models
from japb_api.currencies.models import Currency
from japb_api.accounts.models import Account
from japb_api.transactions.models import Transaction

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

class ReportAccount(Report):
    account = models.ForeignKey(Account, on_delete=models.CASCADE)

    def calculate_initial_balance(self) -> 'ReportAccount':
        from_date = datetime(year=self.from_date.year, month=self.from_date.month, day=self.from_date.day, hour=0, minute=0, second=0, microsecond=0)
        transactions = Transaction.objects.filter(account=self.account, date__lt=timezone.make_aware(from_date))
        transactions_sum = transactions.aggregate(models.Sum('amount'))['amount__sum']
        self.initial_balance = transactions_sum if transactions_sum else 0
        return self
    

    def calculate_end_balance(self) -> 'ReportAccount':
        to_date = datetime(year=self.to_date.year, month=self.to_date.month, day=self.to_date.day, hour=23, minute=59, second=59, microsecond=999999)
        transactions = Transaction.objects.filter(account=self.account, date__lte=timezone.make_aware(to_date))
        transactions_sum = transactions.aggregate(models.Sum('amount'))['amount__sum']
        self.end_balance = transactions_sum if transactions_sum else 0
        return self

    def calculate_total_income(self) -> 'ReportAccount':
        from_date = datetime(year=self.from_date.year, month=self.from_date.month, day=self.from_date.day, hour=0, minute=0, second=0, microsecond=0)
        to_date = datetime(year=self.to_date.year, month=self.to_date.month, day=self.to_date.day, hour=23, minute=59, second=59, microsecond=999999)
        transactions = Transaction.objects.filter(account=self.account, date__range=[from_date, timezone.make_aware(to_date)], amount__gt=0)
        transactions_sum = transactions.aggregate(models.Sum('amount'))['amount__sum']
        self.total_income = transactions_sum if transactions_sum else 0
        return self
    
    def calculate_total_expenses(self) -> 'ReportAccount':
        from_date = datetime(year=self.from_date.year, month=self.from_date.month, day=self.from_date.day, hour=0, minute=0, second=0, microsecond=0)
        to_date = datetime(year=self.to_date.year, month=self.to_date.month, day=self.to_date.day, hour=23, minute=59, second=59, microsecond=999999)
        transactions = Transaction.objects.filter(account=self.account, date__range=[from_date, timezone.make_aware(to_date)], amount__lt=0)
        transactions_sum = transactions.aggregate(models.Sum('amount'))['amount__sum']
        self.total_expenses = transactions_sum if transactions_sum else 0
        return self

class ReportCurrency(Report):
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE)

    def calculate_initial_balance(self) -> 'ReportCurrency':
        reports = ReportAccount.objects.filter(
            account__currency=self.currency,
            from_date__range=[self.from_date, self.to_date]
        )
        reports_sum = reports.aggregate(models.Sum('initial_balance'))['initial_balance__sum']
        self.initial_balance = reports_sum if reports_sum else 0
        return self

    def calculate_end_balance(self) -> 'ReportCurrency':
        reports = ReportAccount.objects.filter(
            account__currency=self.currency,
            from_date__range=[self.from_date, self.to_date]
        )
        reports_sum = reports.aggregate(models.Sum('end_balance'))['end_balance__sum']
        self.end_balance = reports_sum if reports_sum else 0
        return self

    def calculate_total_income(self) -> 'ReportCurrency':
        reports = ReportAccount.objects.filter(
            account__currency=self.currency,
            from_date__range=[self.from_date, self.to_date],
        )
        reports_sum = reports.aggregate(models.Sum('total_income'))['total_income__sum']
        self.total_income = reports_sum if reports_sum else 0
        return self
    
    def calculate_total_expenses(self) -> 'ReportCurrency':
        reports = ReportAccount.objects.filter(
            account__currency=self.currency,
            from_date__range=[self.from_date, self.to_date],
        )
        reports_sum = reports.aggregate(models.Sum('total_expenses'))['total_expenses__sum']
        self.total_expenses = reports_sum if reports_sum else 0
        return self
