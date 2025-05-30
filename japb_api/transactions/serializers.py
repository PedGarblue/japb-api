import django_filters
from rest_framework import serializers
from .models import Transaction, CurrencyExchange, ExchangeComission, Category, TransactionItem
from japb_api.accounts.models import Account


class TransactionItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionItem
        fields = ['id', 'product', 'quantity', 'price', 'total_price']
        read_only_fields = ['id']


class TransactionSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    transaction_items = TransactionItemSerializer(source='transactionitem_set', many=True, required=False)

    class Meta:
        model = Transaction
        fields = [
            "id",
            "user",
            "amount",
            "to_main_currency_amount",
            "description",
            "account",
            "category",
            "date",
            "transaction_items",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        transaction_items_data = None
        if 'transactionitem_set' in validated_data:
            transaction_items_data = validated_data.pop('transactionitem_set')

        transaction = Transaction.objects.create(**validated_data)

        if transaction_items_data:
            for transaction_item_data in transaction_items_data:
                TransactionItem.objects.create(transaction=transaction, **transaction_item_data)

        return transaction

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        amount = rep.get("amount") / (10**instance.account.decimal_places)
        rep["amount"] = f"{amount:.{instance.account.decimal_places}f}"
        if instance.to_main_currency_amount:
            to_main_currency_amount = instance.to_main_currency_amount / (
                10**instance.account.decimal_places
            )
            rep["to_main_currency_amount"] = f"{to_main_currency_amount:.2f}"
        return rep

    def update(self, instance, validated_data):
        transaction_items_data = None
        if 'transactionitem_set' in validated_data:
            transaction_items_data = validated_data.pop('transactionitem_set')

        # Update transaction fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Handle transaction items if provided
        if transaction_items_data is not None:
            # Remove existing items if new ones are provided
            instance.transactionitem_set.all().delete()

            # Create new items
            for transaction_item_data in transaction_items_data:
                TransactionItem.objects.create(transaction=instance, **transaction_item_data)

        return instance


class CurrencyExchangeSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = CurrencyExchange
        fields = [
            "id",
            "user",
            "amount",
            "description",
            "account",
            "date",
            "category",
            "related_transaction",
            "type",
        ]
        read_only_fields = ["id"]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        amount = rep.get("amount") / (10**instance.account.decimal_places)
        rep["amount"] = f"{amount:.{instance.account.decimal_places}f}"
        return rep


class ExchangeComissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExchangeComission
        fields = [
            "id",
            "amount",
            "description",
            "account",
            "date",
            "category",
            "exchange_from",
            "exchange_to",
            "user",
            "type",
        ]
        read_only_fields = ["id"]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        amount = rep.get("amount") / (10**instance.account.decimal_places)
        rep["amount"] = f"{amount:.{instance.account.decimal_places}f}"
        return rep


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            "id",
            "user",
            "name",
            "color",
            "description",
            "parent_category",
            "type",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    user = serializers.HiddenField(default=serializers.CurrentUserDefault())


class TransactionFilterSet(django_filters.FilterSet):
    start_date = django_filters.DateTimeFilter(field_name="date", lookup_expr="gte")
    end_date = django_filters.DateTimeFilter(field_name="date", lookup_expr="lte")
    account = django_filters.ModelChoiceFilter(queryset=Account.objects.all())
    exclude_same_currency_exchanges = django_filters.BooleanFilter(
        method="filter_exclude_same_currency_exchanges"
    )
    currency = django_filters.NumberFilter(
        field_name="account__currency", lookup_expr="exact"
    )

    def filter_exclude_same_currency_exchanges(self, queryset, name, value):
        if value:
            queryset = queryset.exclude(
                id__in=CurrencyExchange.objects.filter(
                    # match 'from_same_currency' and 'to_same_currency' types
                    type__in=["from_same_currency", "to_same_currency"]
                )
            )
        return queryset

    class Meta:
        model = Transaction
        fields = (
            "start_date",
            "end_date",
            "account",
            "currency",
            "exclude_same_currency_exchanges",
        )
