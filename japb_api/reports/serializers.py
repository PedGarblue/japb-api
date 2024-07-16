import django_filters
from rest_framework import serializers
from .models import ReportAccount, ReportCurrency
from japb_api.accounts.models import Account
from japb_api.currencies.models import Currency

class ReportAccountSerializer(serializers.ModelSerializer):
    balance_status = serializers.SerializerMethodField()
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    class Meta:
        model = ReportAccount
        fields = [
            'id',
            'user',
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
    
class ReportCurrencySerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    balance_status = serializers.SerializerMethodField()
    class Meta:
        model = ReportCurrency
        fields = [
            'id',
            'user',
            'from_date',
            'to_date',
            'initial_balance',
            'end_balance',
            'balance_status',
            'total_income',
            'total_expenses',
            'currency',
            'created_at',
            'updated_at',
        ]

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
        greater_decimal_places = Account.objects.filter(currency=instance.currency).order_by('-decimal_places').first().decimal_places

        initial_balance = rep.get('initial_balance') / (10 ** greater_decimal_places)
        end_balance = rep.get('end_balance') / (10 ** greater_decimal_places)
        total_income = rep.get('total_income') / (10 ** greater_decimal_places)
        total_expenses = rep.get('total_expenses') / (10 ** greater_decimal_places)

        rep['initial_balance'] = f'{initial_balance:.{greater_decimal_places}f}'
        rep['end_balance'] = f'{end_balance:.{greater_decimal_places}f}'
        rep['total_income'] = f'{total_income:.{greater_decimal_places}f}'
        rep['total_expenses'] = f'{total_expenses:.{greater_decimal_places}f}'

        return rep


class ReportAccountFilterSet(django_filters.FilterSet):
    account = django_filters.ModelChoiceFilter(queryset=Account.objects.all())

    class Meta:
        model = ReportAccount
        fields = ('account',)

class ReportCurrencyFilterSet(django_filters.FilterSet):
    currency = django_filters.ModelChoiceFilter(queryset=Currency.objects.all())

    class Meta:
        model = ReportCurrency
        fields = ('currency',)