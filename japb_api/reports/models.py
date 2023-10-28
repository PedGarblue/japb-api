from datetime import datetime
from django.utils import timezone
from django.db import models
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
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def calculate_initial_balance(self) -> 'Report':
        from_date = datetime(year=self.from_date.year, month=self.from_date.month, day=self.from_date.day, hour=0, minute=0, second=0, microsecond=0)
        transactions = Transaction.objects.filter(account=self.account, date__lt=timezone.make_aware(from_date))
        transactions_sum = transactions.aggregate(models.Sum('amount'))['amount__sum']
        self.initial_balance = transactions_sum if transactions_sum else 0
        return self
    

    def calculate_end_balance(self) -> 'Report':
        to_date = datetime(year=self.to_date.year, month=self.to_date.month, day=self.to_date.day, hour=23, minute=59, second=59, microsecond=999999)
        transactions = Transaction.objects.filter(account=self.account, date__lte=timezone.make_aware(to_date))
        transactions_sum = transactions.aggregate(models.Sum('amount'))['amount__sum']
        self.end_balance = transactions_sum if transactions_sum else 0
        return self

    def calculate_total_income(self) -> 'Report':
        from_date = datetime(year=self.from_date.year, month=self.from_date.month, day=self.from_date.day, hour=0, minute=0, second=0, microsecond=0)
        to_date = datetime(year=self.to_date.year, month=self.to_date.month, day=self.to_date.day, hour=23, minute=59, second=59, microsecond=999999)
        transactions = Transaction.objects.filter(account=self.account, date__range=[from_date, timezone.make_aware(to_date)], amount__gt=0)
        transactions_sum = transactions.aggregate(models.Sum('amount'))['amount__sum']
        self.total_income = transactions_sum if transactions_sum else 0
        return self
    
    def calculate_total_expenses(self) -> 'Report':
        from_date = datetime(year=self.from_date.year, month=self.from_date.month, day=self.from_date.day, hour=0, minute=0, second=0, microsecond=0)
        to_date = datetime(year=self.to_date.year, month=self.to_date.month, day=self.to_date.day, hour=23, minute=59, second=59, microsecond=999999)
        transactions = Transaction.objects.filter(account=self.account, date__range=[from_date, timezone.make_aware(to_date)], amount__lt=0)
        transactions_sum = transactions.aggregate(models.Sum('amount'))['amount__sum']
        self.total_expenses = transactions_sum if transactions_sum else 0
        return self