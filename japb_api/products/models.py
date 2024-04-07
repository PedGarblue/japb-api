from django.db import models
from japb_api.transactions.models import Category

class Product(models.Model):
    status_choices = (
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive')
    )
    name = models.CharField(max_length=500)
    description = models.CharField(max_length=500, blank=True, null=True, default = '')
    cost = models.DecimalField(max_digits=19, decimal_places = 2, default = 0)
    status = models.CharField(max_length=15, choices=status_choices, default='ACTIVE')
    category = models.ForeignKey(Category, on_delete=models.PROTECT, null=True)
    created_at= models.DateTimeField(auto_now_add=True)
    updated_at= models.DateTimeField(auto_now=True)

class ProductList(models.Model):
    name = models.CharField(max_length=500)
    description = models.CharField(max_length=500, blank=True, null=True, default = '')
    created_at= models.DateTimeField(auto_now_add=True)
    updated_at= models.DateTimeField(auto_now=True)

class ProductListItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    product_list = models.ForeignKey(ProductList, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    created_at= models.DateTimeField(auto_now_add=True)
    updated_at= models.DateTimeField(auto_now=True)
