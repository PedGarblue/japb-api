import django_filters
from rest_framework import serializers
from .models import Product, ProductList, ProductListItem

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'description',
            'cost',
            'status',
            'created_at',
            'updated_at'
        ]

class ProductFilterSet(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    description = django_filters.CharFilter(lookup_expr='icontains')
    status = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = Product
        fields = [
            'name',
            'description',
            'status',
        ]
    
class ProductListSerializer(serializers.ModelSerializer):
    total = serializers.SerializerMethodField()

    class Meta:
        model = ProductList
        fields = [
            'id',
            'name',
            'total',
            'description',
            'created_at',
            'updated_at'
        ]
    
    def get_total(self, product_list):
        queryset = ProductListItem.objects.filter(product_list = product_list.id)
        product_list_items = ProductListItemSerializer(queryset, many = True).data
        total = 0
        total = sum([product_list_item['total'] for product_list_item in product_list_items])
        # total is already in the correct format
        return total

class ProductListItemSerializer(serializers.ModelSerializer):
    total = serializers.SerializerMethodField()
    class Meta:
        model = ProductListItem
        fields = [
            'id',
            'product',
            'product_list',
            'quantity',
            'total',
            'created_at',
            'updated_at'
        ]
    
    def get_total(self, product_list_item):
        return product_list_item.quantity * product_list_item.product.cost
