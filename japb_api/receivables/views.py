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
        serializer = self.get_serializer(data=request.data)
        if(serializer.is_valid(raise_exception = True)):
            serializer.save()
            return Response(serializer.data, status.HTTP_201_CREATED)

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
