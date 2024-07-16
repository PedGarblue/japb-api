from django.db.models import Sum
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from japb_api.core.permissions import IsOwner
from japb_api.transactions.models import Transaction
from .models import Account
from .serializers import AccountSerializer

class AccountViewSet(viewsets.ModelViewSet):
    serializer_class = AccountSerializer
    permission_classes = (IsAuthenticated, IsOwner)

    def get_queryset(self):
        return Account.objects.filter(user = self.request.user)