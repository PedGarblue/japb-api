import django_filters
from rest_framework import serializers
from .models import Report
from japb_api.accounts.models import Account

class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = [
            'id',
            'from_date',
            'to_date',
            'initial_balance',
            'end_balance',
            'total_income',
            'total_expenses',
            'account',
            'created_at',
            'updated_at',
        ]
        # read only fields
        read_only_fields = [
            'id',
            'initial_balance',
            'end_balance',
            'total_income',
            'total_expenses',
            'created_at',
            'updated_at',
        ]

class ReportFilterSet(django_filters.FilterSet):
    account = django_filters.ModelChoiceFilter(queryset=Account.objects.all())

    class Meta:
        model = Report
        fields = ('account',)