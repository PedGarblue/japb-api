import logging
from rest_framework import serializers
from django.db.models import Sum
from .models import Account
from japb_api.transactions.models import Transaction

# Serializer for the Account model.
# It includes a calculated field balance which is not part of the model, and is returned by the get_balance function.
class AccountSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()
    user = serializers.HiddenField(default = serializers.CurrentUserDefault())
    class Meta:
        model = Account
        fields = ['id', 'user', 'name', 'currency', 'balance', 'decimal_places']
        read_only_field = ['id', 'created_at', 'balance'],

    # The get_balance method calculates the balance of the account using all currency transactions associated with it.
    # It filters the CurrencyTransaction model for transactions with the current account's id, sums their amounts 
    # using the aggregate method, and returns the balance.
    def get_balance(self, account):
        queryset = Transaction.objects.filter(account = account.id, user = account.user)
        amount_sum = queryset.aggregate(total=Sum('amount', default = 0))['total']
        # the amounts of the accounts where decimal_places is not 2 are divided by decimal_places * 10
        # if the account uses 2 decimal places, return total
        total = amount_sum / (10 ** account.decimal_places)

        # Return as string with the number of decimal places specified in the account
        return f'{total:.{account.decimal_places}f}'