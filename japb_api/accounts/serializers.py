import logging
from rest_framework import serializers
from django.db.models import Sum
from .models import Account

# Serializer for the Account model.
# It includes a calculated field balance which is not part of the model, and is returned by the get_balance function.
class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ['id', 'name','currency']
        read_only_field = ['id', 'created_at'],
