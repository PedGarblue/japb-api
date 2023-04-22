import django_filters
from rest_framework import serializers
from .models import Transaction, CurrencyExchange

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'amount', 'description', 'account', 'date']

class CurrencyExchangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CurrencyExchange
        fields = ['id', 'amount', 'description', 'account', 'date', 'related_transaction']

class TransactionFilterSet(django_filters.FilterSet):
    start_date = django_filters.DateFilter(field_name='date', lookup_expr='gte')
    end_date = django_filters.DateFilter(field_name='date', lookup_expr='lte')
    
    class Meta: 
        model = Transaction
        fields = ('start_date', 'end_date')
        
