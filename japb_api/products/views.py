from django.db import models
from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated

from japb_api.core.permissions import IsOwner
from .models import Product, ProductList, ProductListItem
from .serializers import ProductSerializer,\
    ProductListSerializer,\
    ProductListItemSerializer,\
    ProductFilterSet,\
    ProductListFilterSet,\
    ProductListItemFilterSet\


class ProductsViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = (IsAuthenticated, IsOwner,)
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    ordering_fields = ['category', 'cost', 'created_at', 'updated_at']
    filterset_class = ProductFilterSet

    def get_queryset(self):
        return Product.objects.filter(user=self.request.user)

class ProductsListViewSet(viewsets.ModelViewSet):
    serializer_class = ProductListSerializer
    permission_classes = (IsAuthenticated, IsOwner,)

    def get_queryset(self):
        return ProductList.objects.filter(user=self.request.user)

class ProductListItemViewSet(viewsets.ModelViewSet):
    serializer_class = ProductListItemSerializer
    permission_classes = (IsAuthenticated, IsOwner,)
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filterset_class = ProductListItemFilterSet
    ordering_fields = ['total', 'product__category', 'created_at', 'updated_at']

    def get_queryset(self):
        return ProductListItem.objects.filter(user=self.request.user)\
        .annotate(
            total = models.ExpressionWrapper(
                models.F('quantity') * models.F('product__cost'),
                output_field = models.DecimalField()
            )
        ).all()

