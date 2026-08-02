from django.db import models
from django.core.validators import MinValueValidator
from ..accounts.models import Account


class TransactionGroup(models.Model):
    user = models.ForeignKey("users.User", on_delete=models.CASCADE)
    name = models.CharField(max_length=500)
    date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name}"


class Transaction(models.Model):
    user = models.ForeignKey("users.User", null=True, on_delete=models.CASCADE)
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    receivable = models.ForeignKey(
        "receivables.Receivable",
        related_name="transactions",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    group = models.ForeignKey(
        "TransactionGroup",
        related_name="transactions",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    category = models.ForeignKey("Category", null=True, on_delete=models.SET_NULL)
    amount = models.BigIntegerField()
    description = models.CharField(max_length=500)
    date = models.DateTimeField()
    to_main_currency_amount = models.BigIntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.description} {self.amount}"

class TransactionItem(models.Model):
    transaction = models.ForeignKey("Transaction", on_delete=models.CASCADE)
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE)
    quantity = models.BigIntegerField(default=0, validators=[MinValueValidator(0)])
    # not used for now, the frontend will only ask for the quantity
    price = models.BigIntegerField(null=True)
    total_price = models.BigIntegerField(null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"N: {self.product.name} Q: {self.quantity} P: {self.price} TP: {self.total_price}"

class CurrencyExchange(Transaction):
    TYPE_CHOICES = [
        ("from_same_currency", "from_same_currency"),
        ("from_different_currency", "from_different_currency"),
        ("to_same_currency", "to_same_currency"),
        ("to_different_currency", "to_different_currency"),
    ]
    related_transaction = models.ForeignKey("self", null=True, on_delete=models.CASCADE)
    type = models.CharField(
        max_length=50, choices=TYPE_CHOICES, default="from_same_currency"
    )


class ExchangeComission(Transaction):
    TYPE_CHOICES = [("comission", "comission"), ("profit", "profit")]
    exchange_from = models.ForeignKey(
        "CurrencyExchange",
        related_name="exchange_from",
        null=True,
        on_delete=models.CASCADE,
    )
    exchange_to = models.ForeignKey(
        "CurrencyExchange",
        related_name="exchange_to",
        null=True,
        on_delete=models.CASCADE,
    )
    type = models.CharField(max_length=50, choices=TYPE_CHOICES, default="comission")


class Category(models.Model):
    TYPE_CHOICES = [
        ("expense", "expense"),
        ("income", "income"),
    ]

    # some categories are global and some are user specific
    user = models.ForeignKey("users.User", null=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=50)
    description = models.CharField(max_length=500)
    parent_category = models.ForeignKey("self", null=True, on_delete=models.CASCADE)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES, default="expense")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name}"
