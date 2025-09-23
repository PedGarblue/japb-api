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
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["name"]


class CurrencyConversionViewSet(viewsets.ViewSet):
    permission_classes = (IsAdminOrReadOnly,)

    def list(self, request):
        """
        Return current exchange rates by source currency in the format:
        {
           "VES":  {
                "USD": {
                    "paralelo": 260.13,
                    "bcv": 160.12
                }
             }
        }
        """
        try:
            usd_currency = Currency.objects.get(name="USD")
            ves_currency = Currency.objects.get(name="VES")

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

            result = {"VES": {"USD": {}}}

            if ves_bcv_conversion:
                result["VES"]["USD"]["bcv"] = ves_bcv_conversion.rate

            if ves_conversion:
                result["VES"]["USD"]["paralelo"] = ves_conversion.rate

            return Response(result)

        except Currency.DoesNotExist:
            return Response({"VES": {"USD": {}}})
