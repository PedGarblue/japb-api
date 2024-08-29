from .models import Receivable
from .serializers import ReceivableSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, filters

from japb_api.core.permissions import IsOwner

class ReceivableViewSet(viewsets.ModelViewSet):
    serializer_class = ReceivableSerializer
    permission_classes = (IsAuthenticated, IsOwner,)
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    ordering_fields = ['created_at']
    ordering = ['created_at']

    def get_queryset(self):
        return Receivable.objects.filter(user = self.request.user)
