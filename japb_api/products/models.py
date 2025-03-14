from django.db import models
from japb_api.transactions.models import Category

PERIOD_TYPE_CHOICES = (("NO_PERIOD", "No Period"), ("MONTHLY", "Monthly"))

class Product(models.Model):
    status_choices = (("ACTIVE", "Active"), ("INACTIVE", "Inactive"))
    # some products are global and some are user specific
    user = models.ForeignKey("users.User", null=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=500)
    description = models.CharField(max_length=500, blank=True, null=True, default="")
    cost = models.DecimalField(max_digits=19, decimal_places=2, default=0)
    status = models.CharField(max_length=15, choices=status_choices, default="ACTIVE")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ProductList(models.Model):
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, null=True)
    name = models.CharField(max_length=500)
    period_type = models.CharField(max_length=15, choices=PERIOD_TYPE_CHOICES, default="NO_PERIOD")
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    description = models.CharField(max_length=500, blank=True, null=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ProductListItem(models.Model):
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, null=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    product_list = models.ForeignKey(ProductList, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    quantity_purchased = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
