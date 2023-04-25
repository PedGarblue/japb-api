from django.db import models
from japb_api.accounts.models import Account

class Receivable(models.Model):
    status_choices = (
        ('UNPAID', 'Unpaid'),
        ('PAID', 'Paid')
    )
    description = models.CharField(max_length=500)
    amount_given = models.DecimalField(max_digits=19, decimal_places = 2, default = 0)
    amount_to_receive = models.DecimalField(max_digits=19, decimal_places = 2, default = 0)
    amount_paid = models.DecimalField(max_digits=19, decimal_places = 2, default = 0)
    due_date = models.DateField()
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    contact = models.CharField(max_length=500)
    status = models.CharField(max_length=15, choices=status_choices, default='UNPAID')
    created_at= models.DateTimeField(auto_now_add=True)
    updated_at= models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.contact} {self.amount}'
