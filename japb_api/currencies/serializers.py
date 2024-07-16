from django.db.models import Sum
from rest_framework import serializers
from .models import Currency
from japb_api.accounts.models import Account
from japb_api.accounts.serializers import AccountSerializer

class CurrencySerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()
    class Meta:
        model = Currency
        fields = ['id', 'name', 'symbol', 'balance']
        read_only_field = ['id', 'created_at', 'balance']
    
    def get_balance(self, currency):
        queryset = Account.objects.filter(currency = currency.id, user = self.context['request'].user)
        accounts = AccountSerializer(queryset, many = True).data
        balance_sum = 0
        balance_sum = sum([float(account['balance']) for account in accounts])
        # balance_sum is already in the correct format
        return balance_sum
