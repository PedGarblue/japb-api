from django.db import models
from ..currencies.models import Currency


class Account(models.Model):
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, null=True)
    name = models.CharField(max_length=100)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    decimal_places = models.IntegerField(default=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name}"
