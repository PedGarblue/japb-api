from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated

from japb_api.core.permissions import IsOwner
from .models import Account
from .serializers import AccountSerializer

class AccountViewSet(viewsets.ModelViewSet):
    serializer_class = AccountSerializer
    permission_classes = (IsAuthenticated, IsOwner)
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    ordering_fields = ['name', 'created_at', 'updated_at']
    ordering = ['name']


    def get_queryset(self):
        return Account.objects.filter(user = self.request.user)