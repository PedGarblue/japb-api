import django_filters
from rest_framework import serializers
from .models import Transaction, CurrencyExchange
from japb_api.accounts.models import Account

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'amount', 'description', 'account', 'date']

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        amount = rep.get('amount') / (10 ** instance.account.decimal_places)
        rep['amount'] = f'{amount:.{instance.account.decimal_places}f}'
        return rep

class CurrencyExchangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CurrencyExchange
        fields = ['id', 'amount', 'description', 'account', 'date', 'related_transaction']

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        amount = rep.get('amount') / (10 ** instance.account.decimal_places)
        rep['amount'] = f'{amount:.{instance.account.decimal_places}f}'
        return rep

class TransactionFilterSet(django_filters.FilterSet):
    start_date = django_filters.DateTimeFilter(field_name='date', lookup_expr='gte')
    end_date = django_filters.DateTimeFilter(field_name='date', lookup_expr='lte')
    account = django_filters.ModelChoiceFilter(queryset=Account.objects.all())
    
    class Meta: 
        model = Transaction
        fields = ('start_date', 'end_date', 'account')
        
