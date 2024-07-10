from django.db import models
from ..accounts.models import Account

class Transaction(models.Model):
    user = models.ForeignKey('users.User', null=True, on_delete=models.CASCADE)
    amount = models.IntegerField()
    description = models.CharField(max_length=500)
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    date = models.DateTimeField()
    category = models.ForeignKey('Category', null = True, on_delete=models.SET_NULL)
    created_at= models.DateTimeField(auto_now_add=True)
    updated_at= models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.description} {self.amount}'

class CurrencyExchange(Transaction):
    TYPE_CHOICES = [
        ('from_same_currency', 'from_same_currency'),
        ('from_different_currency', 'from_different_currency'),
        ('to_same_currency', 'to_same_currency'),
        ('to_different_currency', 'to_different_currency'),
    ]
    related_transaction = models.ForeignKey('self', null = True, on_delete=models.CASCADE)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES, default='from_same_currency')

class ExchangeComission(Transaction):
    TYPE_CHOICES = [
        ('comission', 'comission'),
        ('profit', 'profit')
    ]
    exchange_from = models.ForeignKey('CurrencyExchange', related_name='exchange_from', null = True, on_delete=models.CASCADE)
    exchange_to = models.ForeignKey('CurrencyExchange', related_name='exchange_to', null = True, on_delete=models.CASCADE)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES, default='comission')

class Category(models.Model):
    TYPE_CHOICES = [
        ('expense', 'expense'),
        ('income', 'income'),
    ]

    # some categories are global and some are user specific
    user = models.ForeignKey('users.User', null = True, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=50)
    description = models.CharField(max_length=500)
    parent_category = models.ForeignKey('self', null = True, on_delete=models.CASCADE)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES, default='expense')
    created_at= models.DateTimeField(auto_now_add=True)
    updated_at= models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name}'