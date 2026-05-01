from .models import Currency, CurrencyConversionHistorial
from .serializers import CurrencySerializer
from rest_framework import viewsets, filters
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from japb_api.core.permissions import IsAdminOrReadOnly


class CurrencyViewSet(viewsets.ModelViewSet):
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer
    permission_classes = (IsAdminOrReadOnly,)
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filterset_fields = ["asset_kind"]
    ordering_fields = ["name", "asset_kind", "created_at", "updated_at"]
    ordering = ["name"]


class CurrencyConversionViewSet(viewsets.ViewSet):
    permission_classes = (IsAdminOrReadOnly,)

    def list(self, request):
        """
        Return current exchange rates by source currency in the format:
        {
           "VES":  {
                "USD": {
                    "rates": {
                        "paralelo": 260.13,
                        "bcv": 160.12
                    },
                    "gap": 38.45
                },
                "EUR": {
                    "rates": {
                        "bcv": 210.12
                    },
                    "gap": 19.23
                }
             }
        }
        """
        try:
            usd_currency = Currency.objects.get(name="USD")
            ves_currency = Currency.objects.get(name="VES")
            eur_currency = Currency.objects.get(name="EUR")

            result = {
                "VES": {
                    "USD": {"rates": {}},
                    "EUR": {"rates": {}}
                }
            }

            # VES to USD conversions
            # Get latest VES to USD rate (paralelo source)
            ves_conversion = (
                CurrencyConversionHistorial.objects.filter(
                    currency_from=ves_currency,
                    currency_to=usd_currency,
                    source="paralelo",
                )
                .order_by("-date")
                .first()
            )

            # Get latest VES to USD rate (BCV source)
            ves_bcv_conversion = (
                CurrencyConversionHistorial.objects.filter(
                    currency_from=ves_currency, currency_to=usd_currency, source="bcv"
                )
                .order_by("-date")
                .first()
            )

            if ves_bcv_conversion:
                result["VES"]["USD"]["rates"]["bcv"] = ves_bcv_conversion.rate

            if ves_conversion:
                result["VES"]["USD"]["rates"]["paralelo"] = ves_conversion.rate

            # Calculate gap if both VES rates are available
            if ves_bcv_conversion and ves_conversion:
                gap = (
                    (ves_conversion.rate - ves_bcv_conversion.rate) / ves_conversion.rate
                ) * 100
                result["VES"]["USD"]["gap"] = round(gap, 2)

            # VES to EUR conversions
            # Get latest VES to EUR rate (BCV source)
            ves_eur_conversion = (
                CurrencyConversionHistorial.objects.filter(
                    currency_from=ves_currency, currency_to=eur_currency, source="bcv"
                )
                .order_by("-date")
                .first()
            )

            if ves_eur_conversion:
                result["VES"]["EUR"]["rates"]["bcv"] = ves_eur_conversion.rate

            # Calculate EUR gap if both VES->EUR (BCV) and VES->USD (paralelo) rates are available
            if ves_eur_conversion and ves_conversion:
                gap = (
                    (ves_conversion.rate - ves_eur_conversion.rate) / ves_conversion.rate
                ) * 100
                result["VES"]["EUR"]["gap"] = round(gap, 2)

            return Response(result)

        except Currency.DoesNotExist:
            return Response({
                "VES": {
                    "USD": {"rates": {}},
                    "EUR": {"rates": {}}
                }
            })
