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
        transactions = Transaction.objects.filter(account=self.account, date__lt=self.from_date)
        transactions_sum = transactions.aggregate(models.Sum('amount'))['amount__sum']
        self.initial_balance = transactions_sum if transactions_sum else 0
        return self
    
    def calculate_end_balance(self) -> 'Report':
        transactions = Transaction.objects.filter(account=self.account, date__lte=self.to_date)
        transactions_sum = transactions.aggregate(models.Sum('amount'))['amount__sum']
        self.end_balance = transactions_sum if transactions_sum else 0
        return self

    def calculate_total_income(self) -> 'Report':
        transactions = Transaction.objects.filter(account=self.account, date__range=[self.from_date, self.to_date], amount__gt=0)
        transactions_sum = transactions.aggregate(models.Sum('amount'))['amount__sum']
        self.total_income = transactions_sum if transactions_sum else 0
        return self
    
    def calculate_total_expenses(self) -> 'Report':
        transactions = Transaction.objects.filter(account=self.account, date__range=[self.from_date, self.to_date], amount__lt=0)
        transactions_sum = transactions.aggregate(models.Sum('amount'))['amount__sum']
        self.total_expenses = transactions_sum if transactions_sum else 0
        return self