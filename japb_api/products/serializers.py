import django_filters
from django.db import models
from rest_framework import serializers
from japb_api.transactions.models import Category
from .models import Product, ProductList, ProductListItem


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            "id",
            "user",
            "name",
            "description",
            "cost",
            "status",
            "category",
            "created_at",
            "updated_at",
        ]

    user = serializers.HiddenField(default=serializers.CurrentUserDefault())


class ProductListItemSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    total = serializers.IntegerField(read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_cost = serializers.CharField(source="product.cost", read_only=True)
    product__category = serializers.CharField(source="product.category", read_only=True)
    product_category_color = serializers.CharField(
        source="product.category.color", read_only=True
    )

    class Meta:
        model = ProductListItem
        fields = [
            "id",
            "user",
            "product",
            "product_name",  # this is a read-only field
            "product_cost",  # this is a read-only field
            "product__category",  # this is a read-only field
            "product_category_color",  # this is a read-only field
            "product_list",
            "quantity",
            "quantity_purchased",
            "total",
            "created_at",
            "updated_at",
        ]


class ProductListSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    total = serializers.SerializerMethodField()

    class Meta:
        model = ProductList
        fields = [
            "id",
            "user",
            "name",
            "total",
            "period_type",
            "period_start",
            "period_end",
            "description",
            "created_at",
            "updated_at",
        ]

    def validate(self, data):
        period_type = data.get("period_type")
        period_start = data.get("period_start")
        period_end = data.get("period_end")

        if period_type == "MONTHLY":
            if not period_start:
                raise serializers.ValidationError(
                    "When period_type is MONTHLY, period_start must be provided"
                )
            if not period_end:
                raise serializers.ValidationError(
                    "When period_type is MONTHLY, period_end must be provided"
                )
        elif period_type == "NO_PERIOD":
            if period_start:
                raise serializers.ValidationError(
                    "When period_type is NO_PERIOD, period_start should not be set"
                )
            if period_end:
                raise serializers.ValidationError(
                    "When period_type is NO_PERIOD, period_end should not be set"
                )

        return data

    def get_total(self, product_list):
        queryset = ProductListItem.objects.annotate(
            total=models.ExpressionWrapper(
                models.F("quantity") * models.F("product__cost"),
                output_field=models.DecimalField(),
            )
        ).filter(product_list=product_list.id)
        product_list_items = ProductListItemSerializer(queryset, many=True).data
        total = 0
        total = sum(
            [product_list_item["total"] for product_list_item in product_list_items]
        )
        # total is already in the correct format
        return total


class ProductFilterSet(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")
    description = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.CharFilter(lookup_expr="icontains")
    category = django_filters.ModelChoiceFilter(queryset=Category.objects.all())
    min_price = django_filters.NumberFilter(field_name="cost", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="cost", lookup_expr="lte")

    class Meta:
        model = Product
        fields = [
            "name",
            "description",
            "category",
            "status",
        ]


class ProductListFilterSet(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")
    description = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = ProductList
        fields = [
            "name",
            "description",
        ]


class ProductListItemFilterSet(django_filters.FilterSet):
    product_name = django_filters.CharFilter(lookup_expr="icontains")
    product_list = django_filters.NumberFilter()

    class Meta:
        model = ProductListItem
        fields = [
            "product_name",
            "product_list",
        ]
