from django.db import models
from ..accounts.models import Account
class Transaction(models.Model):
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
    related_transaction = models.ForeignKey('self', null = True, on_delete=models.CASCADE)

class Category(models.Model):
    TYPE_CHOICES = [
        ('expense', 'expense'),
        ('income', 'income'),
    ]

    name = models.CharField(max_length=50)
    color = models.CharField(max_length=50)
    description = models.CharField(max_length=500)
    parent_category = models.ForeignKey('self', null = True, on_delete=models.CASCADE)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES, default='expense')
    created_at= models.DateTimeField(auto_now_add=True)
    updated_at= models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name}'