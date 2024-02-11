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

class ProductListItemSerializer(serializers.ModelSerializer):
    total = serializers.SerializerMethodField()
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_cost = serializers.CharField(source='product.cost', read_only=True)
    class Meta:
        model = ProductListItem
        fields = [
            'id',
            'product',
            'product_name', # this is a read-only field
            'product_cost', # this is a read-only field
            'product_list',
            'quantity',
            'total',
            'created_at',
            'updated_at'
        ]
    
    def get_total(self, product_list_item):
        return product_list_item.quantity * product_list_item.product.cost

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

class ProductListFilterSet(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    description = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = ProductList
        fields = [
            'name',
            'description',
        ]

class ProductListItemFilterSet(django_filters.FilterSet):
    product_name = django_filters.CharFilter(lookup_expr='icontains')
    product_list = django_filters.NumberFilter()

    class Meta:
        model = ProductListItem
        fields = [
            'product_name',
            'product_list',
        ]