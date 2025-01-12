from django.db.models import Sum
from rest_framework import serializers
from .models import Currency, CurrencyConversionHistorial
from japb_api.accounts.models import Account
from japb_api.accounts.serializers import AccountSerializer

class CurrencySerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()
    balance_as_main_currency = serializers.SerializerMethodField()
    latest_conversion_rate_to_main = serializers.SerializerMethodField()
    class Meta:
        model = Currency
        fields = ['id', 'name', 'symbol', 'balance', 'balance_as_main_currency', 'latest_conversion_rate_to_main']
        read_only_field = ['id', 'created_at', 'balance']

    def get_latest_conversion_rate_to_main(self, currency):
        queryset = CurrencyConversionHistorial.objects.filter(currency_from = currency.id, currency_to = Currency.objects.get(name = 'USD'))
        conversion = queryset.order_by('-date').first()
        if conversion:
            return conversion.rate
        else:
            return None
        
    def get_balance(self, currency):
        queryset = Account.objects.filter(currency = currency.id, user = self.context['request'].user)
        accounts = AccountSerializer(queryset, many = True).data
        return sum([float(account['balance']) for account in accounts])

    def get_balance_as_main_currency(self, currency):
        balance = self.get_balance(currency)
        conversion = self.get_latest_conversion_rate_to_main(currency)
        if not conversion:
            return None

        return balance / conversion

    def to_representation(self, instance):
        rep = super().to_representation(instance)

        Accounts = Account.objects.filter(currency = instance.id, user = self.context['request'].user)
        max_decimal_places = max([account.decimal_places for account in Accounts])
        
        rep['balance'] = f'{rep["balance"]:.{max_decimal_places}f}'
        if rep['balance_as_main_currency']:
            rep['balance_as_main_currency'] = f'{rep["balance_as_main_currency"]:.{max_decimal_places}f}'
        return rep
    
