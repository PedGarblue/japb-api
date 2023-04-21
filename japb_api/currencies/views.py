from .models import Currency
from .serializers import CurrencySerializer
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny


class CurrencyViewSet(viewsets.ModelViewSet):
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer
    permission_classes = (AllowAny,)

    def list(self, request):
        qs = self.get_queryset()
        serializer = CurrencySerializer(qs, many=True)
        return Response(serializer.data)

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        if(serializer.is_valid(raise_exception = True)):
            serializer.save()
            return Response(serializer.data, status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        try:
            item = Currency.objects.get(pk = pk)
        except Exception as e:
            return Response(status = status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(item)
        return Response(serializer.data)

    def update(self, request, pk=None):
        try:
            item = Currency.objects.get(pk = pk)
        except Exception as e:
            return Response(status = status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(item, data = request.data)

        if(serializer.is_valid(raise_exception = True)):
            serializer.save()
            return Response(serializer.data)
        
        return Response(serializer.data)

    @action(detail=True, methods=['delete'])
    def delete(self, request, pk=None):
        try:
            item = Currency.objects.get(pk = pk)
        except Exception as e:
            return Response(status = status.HTTP_404_NOT_FOUND)

        item.delete()

        return Response(status = status.HTTP_204_NO_CONTENT)
