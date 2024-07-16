from .models import Currency
from .serializers import CurrencySerializer
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny

from japb_api.core.permissions import IsAdminOrReadOnly


class CurrencyViewSet(viewsets.ModelViewSet):
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer
    permission_classes = (IsAdminOrReadOnly,)
