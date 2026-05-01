from rest_framework import serializers

from .models import AssetKind, Currency, CurrencyConversionHistorial
from japb_api.accounts.models import Account
from japb_api.accounts.serializers import AccountSerializer


class CurrencySerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()
    balance_as_main_currency = serializers.SerializerMethodField()
    latest_conversion_rate_to_main = serializers.SerializerMethodField()
    default_decimal_places = serializers.IntegerField(
        required=False, min_value=0, max_value=28
    )

    class Meta:
        model = Currency
        fields = [
            "id",
            "name",
            "symbol",
            "asset_kind",
            "default_decimal_places",
            "balance",
            "balance_as_main_currency",
            "latest_conversion_rate_to_main",
        ]
        read_only_field = ["id", "created_at", "balance"]

    def create(self, validated_data):
        if "default_decimal_places" not in validated_data:
            asset_kind = validated_data.get("asset_kind", AssetKind.FIAT)
            validated_data["default_decimal_places"] = (
                Currency.infer_default_decimal_places(asset_kind)
            )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        asset_kind = validated_data.get("asset_kind", instance.asset_kind)
        if "default_decimal_places" not in validated_data:
            if "asset_kind" in validated_data:
                validated_data["default_decimal_places"] = (
                    Currency.infer_default_decimal_places(asset_kind)
                )
        return super().update(instance, validated_data)

    def get_latest_conversion_rate_to_main(self, currency):
        if not Currency.objects.filter(name="USD").exists():
            return None

        queryset = CurrencyConversionHistorial.objects.filter(
            currency_from=currency.id,
            currency_to__name="USD",
            source=currency.default_conversion_source,
        )

        conversion = queryset.order_by("-date").first()

        if conversion:
            return conversion.rate
        else:
            return None

    def get_balance(self, currency):
        queryset = Account.objects.filter(
            currency=currency.id, user=self.context["request"].user
        )
        accounts = AccountSerializer(queryset, many=True).data
        return sum([float(account["balance"]) for account in accounts])

    def get_balance_as_main_currency(self, currency):
        balance = self.get_balance(currency)
        conversion = self.get_latest_conversion_rate_to_main(currency)
        if not conversion:
            return None

        return balance / conversion

    def to_representation(self, instance):
        rep = super().to_representation(instance)

        accounts = Account.objects.filter(
            currency=instance.id, user=self.context["request"].user
        )
        max_decimal_places = 2  # Default decimal places
        if accounts.exists():
            max_decimal_places = max([account.decimal_places for account in accounts])

        rep["balance"] = f'{rep["balance"]:.{max_decimal_places}f}'
        if rep["balance_as_main_currency"]:
            rep[
                "balance_as_main_currency"
            ] = f'{rep["balance_as_main_currency"]:.{max_decimal_places}f}'
        return rep
