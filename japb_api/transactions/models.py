from django.db import models
from ..accounts.models import Account
class Transaction(models.Model):
    amount = models.DecimalField(max_digits=19, decimal_places = 2)
    description = models.CharField(max_length=500)
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    date = models.DateTimeField()
    created_at= models.DateTimeField(auto_now_add=True)
    updated_at= models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.description} {self.amount}'

class CurrencyExchange(Transaction):
    related_transaction = models.ForeignKey('self', null = True, on_delete=models.CASCADE)