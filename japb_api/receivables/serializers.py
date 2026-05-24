from rest_framework import serializers

from japb_api.transactions.models import Transaction
from japb_api.transactions.utils import convert_transaction_to_usd

from .models import Contact, Receivable
from .utils import (
    compute_contact_totals,
    compute_receivable_totals,
    get_or_create_contact,
    get_usd_currency,
)


class ReceivableLinkedTransactionSerializer(serializers.ModelSerializer):
    amount_display = serializers.SerializerMethodField()
    usd_amount = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            "id",
            "account",
            "amount_display",
            "date",
            "description",
            "usd_amount",
        ]

    def get_amount_display(self, obj):
        dp = obj.account.decimal_places
        amt = obj.amount / (10**dp)
        return f"{amt:.{dp}f}"

    def get_usd_amount(self, obj):
        usd_currency = self.context.get("usd_currency")
        usd, err = convert_transaction_to_usd(obj, usd_currency)
        if err:
            return None
        return round(usd, 2)


class ReceivableSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    contact = serializers.CharField(write_only=True, max_length=500)
    contact_id = serializers.IntegerField(source="contact.id", read_only=True)
    contact_name = serializers.CharField(source="contact.name", read_only=True)

    class Meta:
        model = Receivable
        fields = [
            "id",
            "user",
            "description",
            "contact",
            "contact_id",
            "contact_name",
            "due_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["contact_id", "contact_name"]

    def create(self, validated_data):
        contact_name = validated_data.pop("contact")
        user = validated_data["user"]
        validated_data["contact"] = get_or_create_contact(user, contact_name)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "contact" in validated_data:
            contact_name = validated_data.pop("contact")
            validated_data["contact"] = get_or_create_contact(
                instance.user, contact_name
            )
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        usd_currency = self.context.get("usd_currency") or get_usd_currency()

        txs = list(
            instance.transactions.select_related("account", "account__currency").order_by(
                "date"
            )
        )

        totals = compute_receivable_totals(instance, usd_currency)
        data.update(totals)
        data["transactions"] = ReceivableLinkedTransactionSerializer(
            txs,
            many=True,
            context={**self.context, "usd_currency": usd_currency},
        ).data
        return data


class ContactSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    total_principal_usd = serializers.SerializerMethodField()
    total_paid_usd = serializers.SerializerMethodField()
    total_outstanding_usd = serializers.SerializerMethodField()
    receivable_count = serializers.SerializerMethodField()

    class Meta:
        model = Contact
        fields = [
            "id",
            "user",
            "name",
            "created_at",
            "updated_at",
            "total_principal_usd",
            "total_paid_usd",
            "total_outstanding_usd",
            "receivable_count",
        ]

    def get_receivables_queryset(self, obj):
        return obj.receivables.prefetch_related(
            "transactions__account__currency"
        ).all()

    def get_totals(self, obj):
        if not hasattr(obj, "_contact_totals"):
            usd_currency = self.context.get("usd_currency") or get_usd_currency()
            receivables = list(self.get_receivables_queryset(obj))
            obj._contact_totals = compute_contact_totals(receivables, usd_currency)
            obj._receivable_count = len(receivables)
        return obj._contact_totals

    def get_total_principal_usd(self, obj):
        return self.get_totals(obj)["total_principal_usd"]

    def get_total_paid_usd(self, obj):
        return self.get_totals(obj)["total_paid_usd"]

    def get_total_outstanding_usd(self, obj):
        return self.get_totals(obj)["total_outstanding_usd"]

    def get_receivable_count(self, obj):
        self.get_totals(obj)
        return obj._receivable_count


class ContactDetailSerializer(ContactSerializer):
    receivables = serializers.SerializerMethodField()

    class Meta(ContactSerializer.Meta):
        fields = ContactSerializer.Meta.fields + ["receivables"]

    def get_receivables(self, obj):
        usd_currency = self.context.get("usd_currency") or get_usd_currency()
        receivables = self.get_receivables_queryset(obj)
        return ReceivableSerializer(
            receivables,
            many=True,
            context={**self.context, "usd_currency": usd_currency},
        ).data


class ReceivableGroupByContactSerializer(serializers.Serializer):
    contact_id = serializers.IntegerField()
    contact = serializers.CharField()
    total_principal_usd = serializers.FloatField()
    total_paid_usd = serializers.FloatField()
    total_outstanding_usd = serializers.FloatField()
    receivables = ReceivableSerializer(many=True)
