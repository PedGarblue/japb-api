import logging
from rest_framework import serializers
from django.db.models import Sum
from .models import Account
from japb_api.transactions.models import Transaction

# Serializer for the Account model.
# It includes a calculated field balance which is not part of the model, and is returned by the get_balance function.
class AccountSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()
    class Meta:
        model = Account
        fields = ['id', 'name', 'currency', 'balance']
        read_only_field = ['id', 'created_at', 'balance'],

    # The get_balance method calculates the balance of the account using all currency transactions associated with it.
    # It filters the CurrencyTransaction model for transactions with the current account's id, sums their amounts 
    # using the aggregate method, and returns the balance.
    def get_balance(self, account):
        queryset = Transaction.objects.filter(account = account.id)
        total = queryset.aggregate(total=Sum('amount', default = 0))['total']
        # classic problem of floating points in python :^)
        return "%.2f" % total