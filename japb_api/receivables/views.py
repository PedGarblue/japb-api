from .models import Receivable
from .serializers import ReceivableSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets
from japb_api.core.permissions import IsOwner

class ReceivableViewSet(viewsets.ModelViewSet):
    serializer_class = ReceivableSerializer
    permission_classes = (IsAuthenticated, IsOwner,)

    def get_queryset(self):
        return Receivable.objects.filter(user = self.request.user)
