from django.db import models


class AssetKind(models.TextChoices):
    FIAT = "fiat", "Fiat"
    CRYPTO = "crypto", "Crypto"


DEFAULT_DECIMAL_PLACES_FIAT = 2
DEFAULT_DECIMAL_PLACES_CRYPTO = 8


class Currency(models.Model):
    # some currencies are global and some are user specific
    user = models.ForeignKey("users.User", null=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=5, null=True)
    asset_kind = models.CharField(
        max_length=20,
        choices=AssetKind.choices,
        default=AssetKind.FIAT,
        db_index=True,
    )
    default_decimal_places = models.PositiveSmallIntegerField(
        default=DEFAULT_DECIMAL_PLACES_FIAT,
    )
    default_conversion_source = models.CharField(
        max_length=100, null=True
    )

    def __str__(self):
        return self.name

    @classmethod
    def infer_default_decimal_places(cls, asset_kind: str) -> int:
        if asset_kind == AssetKind.CRYPTO:
            return DEFAULT_DECIMAL_PLACES_CRYPTO
        return DEFAULT_DECIMAL_PLACES_FIAT


class CurrencyConversionHistorial(models.Model):
    # some currencies are global and some are user specific
    user = models.ForeignKey("users.User", null=True, on_delete=models.CASCADE)
    currency_from = models.ForeignKey(
        "Currency", related_name="currency_from", on_delete=models.CASCADE
    )
    # always be USD for now
    currency_to = models.ForeignKey(
        "Currency", related_name="currency_to", on_delete=models.CASCADE
    )
    source = models.CharField(
        max_length=100,
        default="paralelo",
        choices=[
            ("paralelo", "Paralelo"),
            ("bcv", "BCV"),
            ("binance_spot", "Binance spot (public)"),
        ],
    )

    rate = models.FloatField()
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.currency_from} to {self.currency_to} - {self.rate}"
