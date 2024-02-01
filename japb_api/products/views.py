from django.http import JsonResponse
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status, viewsets

from .models import Product, ProductList, ProductListItem
from .serializers import ProductSerializer, ProductFilterSet, ProductListSerializer, ProductListItemSerializer

class ProductsViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = (AllowAny,)

class ProductsListViewSet(viewsets.ModelViewSet):
    queryset = ProductList.objects.all()
    serializer_class = ProductListSerializer
    permission_classes = (AllowAny,)

class ProductListItemViewSet(viewsets.ModelViewSet):
    queryset = ProductListItem.objects.all()
    serializer_class = ProductListItemSerializer
    permission_classes = (AllowAny,)
