import django_filters
from rest_framework import serializers
from .models import (
    Transaction,
    TransactionGroup,
    CurrencyExchange,
    ExchangeComission,
    Category,
    TransactionItem,
)
from japb_api.accounts.models import Account
from japb_api.receivables.models import Receivable


class TransactionItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionItem
        fields = ['id', 'product', 'quantity', 'price', 'total_price']
        read_only_fields = ['id']


class TransactionGroupListSerializer(serializers.Serializer):
    """Collapsed group row for the mixed transaction list feed."""

    type = serializers.SerializerMethodField()
    id = serializers.IntegerField()
    name = serializers.CharField()
    date = serializers.DateTimeField()
    transaction_count = serializers.SerializerMethodField()
    total_main_currency_amount = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()

    def get_type(self, obj):
        return "group"

    def get_transaction_count(self, obj):
        if hasattr(obj, "annotated_transaction_count"):
            return obj.annotated_transaction_count
        return obj.transactions.count()

    def _members(self, obj):
        return list(obj.transactions.all())

    def _single_non_usd_currency(self, members):
        """Return (currency_name, decimal_places) when all members share one non-USD currency."""
        if not members:
            return None
        currency_ids = {m.account.currency_id for m in members}
        if len(currency_ids) != 1:
            return None
        currency = members[0].account.currency
        if currency.name == "USD":
            return None
        decimal_places = max(m.account.decimal_places for m in members)
        return currency.name, decimal_places

    def get_total_main_currency_amount(self, obj):
        members = self._members(obj)
        if not members:
            return None
        if any(m.to_main_currency_amount is None for m in members):
            return None
        total = sum(m.to_main_currency_amount for m in members)
        return f"{total / 100:.2f}"

    def get_total_amount(self, obj):
        members = self._members(obj)
        info = self._single_non_usd_currency(members)
        if info is None:
            return None
        _, decimal_places = info
        total = sum(
            m.amount / (10 ** m.account.decimal_places) for m in members
        )
        return f"{total:.{decimal_places}f}"

    def get_currency(self, obj):
        members = self._members(obj)
        info = self._single_non_usd_currency(members)
        if info is None:
            return None
        return info[0]


class TransactionSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    transaction_items = TransactionItemSerializer(source='transactionitem_set', many=True, required=False)
    receivable = serializers.PrimaryKeyRelatedField(
        queryset=Receivable.objects.all(),
        allow_null=True,
        required=False,
    )
    group = serializers.PrimaryKeyRelatedField(read_only=True)
    group_id = serializers.IntegerField(
        write_only=True, required=False, allow_null=True
    )
    is_loan = serializers.BooleanField(required=False, default=False, write_only=True)
    contact = serializers.CharField(required=False, allow_blank=True, write_only=True, max_length=500)
    loan_due_date = serializers.DateField(required=False, allow_null=True, write_only=True)

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
            "receivable",
            "group",
            "group_id",
            "is_loan",
            "contact",
            "loan_due_date",
        ]
        read_only_fields = ["id", "group"]

    def validate_receivable(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        if request and str(value.user_id) != str(request.user.id):
            raise serializers.ValidationError("Invalid receivable.")
        return value

    def validate_group_id(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        try:
            group = TransactionGroup.objects.get(pk=value)
        except TransactionGroup.DoesNotExist:
            raise serializers.ValidationError("Invalid group.")
        if request and str(group.user_id) != str(request.user.id):
            raise serializers.ValidationError("Invalid group.")
        return value

    def create(self, validated_data):
        validated_data.pop("is_loan", None)
        validated_data.pop("contact", None)
        validated_data.pop("loan_due_date", None)
        group_id = validated_data.pop("group_id", None)
        transaction_items_data = None
        if 'transactionitem_set' in validated_data:
            transaction_items_data = validated_data.pop('transactionitem_set')

        # Prefer explicit group set by the view (new group create); else bind via group_id
        if "group" not in validated_data and group_id is not None:
            validated_data["group_id"] = group_id

        transaction = Transaction.objects.create(**validated_data)

        if transaction_items_data:
            for transaction_item_data in transaction_items_data:
                TransactionItem.objects.create(transaction=transaction, **transaction_item_data)

        return transaction

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep["type"] = "transaction"
        amount = rep.get("amount") / (10**instance.account.decimal_places)
        rep["amount"] = f"{amount:.{instance.account.decimal_places}f}"
        if instance.to_main_currency_amount:
            to_main_currency_amount = instance.to_main_currency_amount / (
                10**instance.account.decimal_places
            )
            rep["to_main_currency_amount"] = f"{to_main_currency_amount:.2f}"
        rep["receivable"] = instance.receivable_id
        rep["group"] = instance.group_id
        if instance.receivable_id:
            rep["contact"] = instance.receivable.contact.name
            rep["contact_id"] = instance.receivable.contact_id
        return rep

    def update(self, instance, validated_data):
        validated_data.pop("is_loan", None)
        validated_data.pop("contact", None)
        validated_data.pop("loan_due_date", None)
        group_id = validated_data.pop("group_id", serializers.empty)
        transaction_items_data = None
        if 'transactionitem_set' in validated_data:
            transaction_items_data = validated_data.pop('transactionitem_set')

        # Update transaction fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if group_id is not serializers.empty:
            instance.group_id = group_id
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
    category = django_filters.ModelChoiceFilter(
        queryset=Category.objects.all(), method="filter_category"
    )
    group = django_filters.ModelChoiceFilter(queryset=TransactionGroup.objects.all())
    exclude_children = django_filters.BooleanFilter(method="filter_exclude_children")
    exclude_same_currency_exchanges = django_filters.BooleanFilter(
        method="filter_exclude_same_currency_exchanges"
    )
    currency = django_filters.NumberFilter(
        field_name="account__currency", lookup_expr="exact"
    )

    def filter_category(self, queryset, name, value):
        if value:
            # Check if exclude_children is set in the query parameters
            exclude_children = False
            # Try to get exclude_children from form data or raw data
            if hasattr(self, "form") and hasattr(self.form, "data"):
                exclude_children_str = self.form.data.get("exclude_children", "").lower()
                exclude_children = exclude_children_str in ("true", "1", "yes")
            elif hasattr(self, "data") and self.data:
                exclude_children_str = self.data.get("exclude_children", "").lower()
                exclude_children = exclude_children_str in ("true", "1", "yes")
            
            if exclude_children:
                # Only include transactions with the exact category (no children)
                queryset = queryset.filter(category=value)
            else:
                # Include transactions with the category or any of its children
                child_categories = Category.objects.filter(parent_category=value)
                category_ids = [value.id] + list(child_categories.values_list("id", flat=True))
                queryset = queryset.filter(category__in=category_ids)
        return queryset

    def filter_exclude_children(self, queryset, name, value):
        # This filter is handled within filter_category method
        # We don't need to do anything here, but we keep it for the API
        return queryset

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
            "category",
            "group",
            "exclude_children",
            "currency",
            "exclude_same_currency_exchanges",
        )
