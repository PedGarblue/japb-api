from django.db import models
from django.http import JsonResponse
from rest_framework import status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend

from .models import Product, ProductList, ProductListItem
from .serializers import ProductSerializer,\
    ProductListSerializer,\
    ProductListItemSerializer,\
    ProductFilterSet,\
    ProductListFilterSet,\
    ProductListItemFilterSet\


class ProductsViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = (AllowAny,)
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    ordering_fields = ['category', 'cost', 'created_at', 'updated_at']
    filterset_class = ProductFilterSet

class ProductsListViewSet(viewsets.ModelViewSet):
    queryset = ProductList.objects.all()
    serializer_class = ProductListSerializer
    permission_classes = (AllowAny,)

class ProductListItemViewSet(viewsets.ModelViewSet):
    queryset = ProductListItem.objects.annotate(
        total = models.ExpressionWrapper(
            models.F('quantity') * models.F('product__cost'),
            output_field = models.DecimalField()
        )
    ).all()
    serializer_class = ProductListItemSerializer
    permission_classes = (AllowAny,)
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filterset_class = ProductListItemFilterSet
    ordering_fields = ['total', 'product__category', 'created_at', 'updated_at']

