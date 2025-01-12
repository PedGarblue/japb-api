from rest_framework import serializers
from django.db.models import Sum
from .models import Account
from japb_api.transactions.models import Transaction
from japb_api.currencies.models import Currency, CurrencyConversionHistorial

# Serializer for the Account model.
# It includes a calculated field balance which is not part of the model, and is returned by the get_balance function.
class AccountSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()
    balance_as_main_currency = serializers.SerializerMethodField()
    latest_conversion_rate_to_main = serializers.SerializerMethodField()

    user = serializers.HiddenField(default = serializers.CurrentUserDefault())
    class Meta:
        model = Account
        fields = ['id', 'user', 'name', 'currency', 'balance', 'balance_as_main_currency', 'latest_conversion_rate_to_main', 'decimal_places']
        read_only_field = ['id', 'created_at', 'balance', 'balance_as_main_currency'],

    def get_latest_conversion_rate_to_main(self, account):
        queryset = CurrencyConversionHistorial.objects.filter(currency_from = account.currency.id, currency_to = Currency.objects.get(name = 'USD'))
        conversion = queryset.order_by('-date').first()
        if conversion:
            return conversion.rate
        else:
            return None

    # The get_balance method calculates the balance of the account using all currency transactions associated with it.
    # It filters the CurrencyTransaction model for transactions with the current account's id, sums their amounts 
    # using the aggregate method, and returns the balance.
    def get_balance(self, account):
        queryset = Transaction.objects.filter(account = account.id, user = account.user)
        amount_sum = queryset.aggregate(total=Sum('amount', default = 0))['total']
        # the amounts of the accounts where decimal_places is not 2 are divided by decimal_places * 10
        # if the account uses 2 decimal places, return total
        return amount_sum / (10 ** account.decimal_places)

    def get_balance_as_main_currency(self, account):
        conversion = self.get_latest_conversion_rate_to_main(account)
        if not conversion:
            return None

        return self.get_balance(account) / conversion

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['balance'] = f'{rep["balance"]:.{instance.decimal_places}f}'
        if rep['balance_as_main_currency']:
            rep['balance_as_main_currency'] = f'{rep["balance_as_main_currency"]:.{instance.decimal_places}f}'
        return rep
