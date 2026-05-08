from rest_framework import serializers

from japb_api.currencies.models import Currency
from japb_api.transactions.models import Transaction
from japb_api.transactions.utils import convert_transaction_to_usd

from .models import Receivable


class ReceivableLinkedTransactionSerializer(serializers.ModelSerializer):
    """Nested transaction summary for a receivable; amounts include USD derived value."""

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

    class Meta:
        model = Receivable
        fields = [
            "id",
            "user",
            "description",
            "contact",
            "due_date",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        usd_currency = Currency.objects.filter(name="USD").first()

        txs = list(
            instance.transactions.select_related("account", "account__currency").order_by(
                "date"
            )
        )

        principal_usd = 0.0
        paid_usd = 0.0
        for tx in txs:
            usd, err = convert_transaction_to_usd(tx, usd_currency)
            if err:
                continue
            if tx.amount < 0:
                principal_usd += abs(usd)
            elif tx.amount > 0:
                paid_usd += usd

        outstanding_usd = principal_usd - paid_usd
        data["principal_usd"] = round(principal_usd, 2)
        data["paid_usd"] = round(paid_usd, 2)
        data["outstanding_usd"] = round(outstanding_usd, 2)
        data["status"] = "PAID" if outstanding_usd <= 0 else "UNPAID"
        data["transactions"] = ReceivableLinkedTransactionSerializer(
            txs,
            many=True,
            context={**self.context, "usd_currency": usd_currency},
        ).data
        return data
