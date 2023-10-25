import django_filters
from rest_framework import serializers
from .models import Report
from japb_api.accounts.models import Account

class ReportSerializer(serializers.ModelSerializer):
    balance_status = serializers.SerializerMethodField()
    class Meta:
        model = Report
        fields = [
            'id',
            'from_date',
            'to_date',
            'initial_balance',
            'end_balance',
            'balance_status',
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

    def get_balance_status(self, report):
        if report.end_balance > report.initial_balance:
            return 'positive'
        elif report.end_balance < report.initial_balance:
            return 'negative'
        else:
            return 'neutral'

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        initial_balance = rep.get('initial_balance') / (10 ** instance.account.decimal_places)
        end_balance = rep.get('end_balance') / (10 ** instance.account.decimal_places)
        total_income = rep.get('total_income') / (10 ** instance.account.decimal_places)
        total_expenses = rep.get('total_expenses') / (10 ** instance.account.decimal_places)

        rep['initial_balance'] = f'{initial_balance:.{instance.account.decimal_places}f}'
        rep['end_balance'] = f'{end_balance:.{instance.account.decimal_places}f}'
        rep['total_income'] = f'{total_income:.{instance.account.decimal_places}f}'
        rep['total_expenses'] = f'{total_expenses:.{instance.account.decimal_places}f}'

        return rep

class ReportFilterSet(django_filters.FilterSet):
    account = django_filters.ModelChoiceFilter(queryset=Account.objects.all())

    class Meta:
        model = Report
        fields = ('account',)