from django.http import JsonResponse
from .models import Receivable
from .serializers import ReceivableSerializer
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status, viewsets

class ReceivableViewSet(viewsets.ModelViewSet):
    queryset = Receivable.objects.all()
    serializer_class = ReceivableSerializer
    permission_classes = (AllowAny,)

    def list(self, request):
        qs = self.get_queryset()
        serializer = ReceivableSerializer(qs, many=True)
        return Response(serializer.data)

    def create(self, request):
        receivables_data = request.data
        if not isinstance(receivables_data, list):
            receivables_data = [receivables_data]

        created_receivables = []
        for receivable_data in receivables_data:
            receivable_serializer = self.get_serializer(data=receivable_data)
            if receivable_serializer.is_valid():
                receivable = receivable_serializer.save()
                created_receivables.append(receivable_serializer.data)
            else:
                return Response(receivable_serializer.errors,
                                status=status.HTTP_400_BAD_REQUEST)

        return Response(created_receivables, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        try:
            item = Receivable.objects.get(pk = pk)
        except Receivable.DoesNotExist:
            return Response(status = status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(item)
        return Response(serializer.data)

    def update(self, request, pk=None):
        try:
            item = Receivable.objects.get(pk = pk)
        except Receivable.DoesNotExist:
            return Response(status = status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(item, data = request.data)

        if(serializer.is_valid(raise_exception = True)):
            serializer.save()
            return Response(serializer.data)
        
        return Response(serializer.data)

    def partial_update(self, request, pk=None):
        try:
            item = Receivable.objects.get(pk=pk)
        except Receivable.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(
            item, data=request.data, partial=True)

        if serializer.is_valid(raise_exception=True):
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk=None):
        try:
            item = Receivable.objects.get(pk = pk)
        except Receivable.DoesNotExist:
            return Response(status = status.HTTP_404_NOT_FOUND)

        item.delete()

        return Response(status = status.HTTP_204_NO_CONTENT)
