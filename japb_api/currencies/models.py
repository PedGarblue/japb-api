from django.db import models


class Currency(models.Model):
    # some currencies are global and some are user specific
    user = models.ForeignKey("users.User", null=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=5, null=True)

    def __str__(self):
        return self.name


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
        choices=[("paralelo", "Paralelo"), ("bcv", "BCV")],
    )

    rate = models.FloatField()
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.currency_from} to {self.currency_to} - {self.rate}"
