from .models import Currency
from .serializers import CurrencySerializer
from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, filters

from japb_api.core.permissions import IsAdminOrReadOnly


class CurrencyViewSet(viewsets.ModelViewSet):
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer
    permission_classes = (IsAdminOrReadOnly,)
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    ordering_fields = ['name', 'created_at', 'updated_at']
    ordering = ['name']
