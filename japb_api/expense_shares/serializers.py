from decimal import Decimal

from rest_framework import serializers

from japb_api.receivables.utils import get_or_create_contact
from japb_api.transactions.models import Category

from .models import (
    ExpenseShareCategoryExclude,
    ExpenseShareCategoryInclude,
    ExpenseShareLine,
    ExpenseSharePartner,
    ExpenseSharePeriod,
)


class ExpenseShareLineSerializer(serializers.ModelSerializer):
    category_id = serializers.IntegerField(source="category.id", read_only=True, allow_null=True)
    category_name = serializers.CharField(
        source="category.name", read_only=True, allow_null=True
    )

    class Meta:
        model = ExpenseShareLine
        fields = [
            "id",
            "category_id",
            "category_name",
            "expense_total_usd",
            "partner_share_usd",
            "transaction_count",
        ]


class ExpenseSharePartnerSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    contact = serializers.CharField(write_only=True, max_length=500)
    contact_id = serializers.IntegerField(source="contact.id", read_only=True)
    contact_name = serializers.CharField(source="contact.name", read_only=True)
    includes = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
    )
    excludes = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
    )
    include_ids = serializers.SerializerMethodField()
    exclude_ids = serializers.SerializerMethodField()

    class Meta:
        model = ExpenseSharePartner
        fields = [
            "id",
            "user",
            "contact",
            "contact_id",
            "contact_name",
            "is_active",
            "default_partner_percent",
            "includes",
            "excludes",
            "include_ids",
            "exclude_ids",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["contact_id", "contact_name", "include_ids", "exclude_ids"]

    def get_include_ids(self, obj):
        return list(obj.includes.values_list("category_id", flat=True))

    def get_exclude_ids(self, obj):
        return list(obj.excludes.values_list("category_id", flat=True))

    def _validate_category_ids(self, category_ids):
        if not category_ids:
            return
        existing = set(
            Category.objects.filter(id__in=category_ids).values_list("id", flat=True)
        )
        missing = set(category_ids) - existing
        if missing:
            raise serializers.ValidationError(
                f"Unknown category ids: {sorted(missing)}"
            )

    def validate_includes(self, value):
        self._validate_category_ids(value)
        return value

    def validate_excludes(self, value):
        self._validate_category_ids(value)
        return value

    def _sync_categories(self, partner, includes, excludes):
        if includes is not None:
            partner.includes.all().delete()
            ExpenseShareCategoryInclude.objects.bulk_create(
                [
                    ExpenseShareCategoryInclude(partner=partner, category_id=cid)
                    for cid in dict.fromkeys(includes)
                ]
            )
        if excludes is not None:
            partner.excludes.all().delete()
            ExpenseShareCategoryExclude.objects.bulk_create(
                [
                    ExpenseShareCategoryExclude(partner=partner, category_id=cid)
                    for cid in dict.fromkeys(excludes)
                ]
            )

    def create(self, validated_data):
        includes = validated_data.pop("includes", None)
        excludes = validated_data.pop("excludes", None)
        contact_name = validated_data.pop("contact")
        user = validated_data["user"]
        contact = get_or_create_contact(user, contact_name)
        partner = ExpenseSharePartner.objects.create(contact=contact, **validated_data)
        self._sync_categories(partner, includes if includes is not None else [], excludes if excludes is not None else [])
        return partner

    def update(self, instance, validated_data):
        includes = validated_data.pop("includes", None)
        excludes = validated_data.pop("excludes", None)
        if "contact" in validated_data:
            contact_name = validated_data.pop("contact")
            instance.contact = get_or_create_contact(instance.user, contact_name)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        self._sync_categories(instance, includes, excludes)
        return instance


class ExpenseSharePeriodSerializer(serializers.ModelSerializer):
    partner_id = serializers.IntegerField(source="partner.id", read_only=True)
    partner_contact_name = serializers.CharField(
        source="partner.contact.name", read_only=True
    )
    receivable_id = serializers.IntegerField(
        source="receivable.id", read_only=True, allow_null=True
    )
    lines = ExpenseShareLineSerializer(many=True, read_only=True)

    class Meta:
        model = ExpenseSharePeriod
        fields = [
            "id",
            "partner_id",
            "partner_contact_name",
            "year",
            "month",
            "status",
            "partner_percent",
            "total_expenses_usd",
            "partner_share_usd",
            "my_share_usd",
            "receivable_id",
            "notes",
            "finalized_at",
            "lines",
            "created_at",
            "updated_at",
        ]


class ExpenseSharePreviewSerializer(serializers.Serializer):
    partner = serializers.IntegerField()
    year = serializers.IntegerField(min_value=2000, max_value=2100)
    month = serializers.IntegerField(min_value=1, max_value=12)
    partner_percent = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True
    )


class ExpenseShareFinalizeSerializer(serializers.Serializer):
    partner = serializers.IntegerField()
    year = serializers.IntegerField(min_value=2000, max_value=2100)
    month = serializers.IntegerField(min_value=1, max_value=12)
    partner_percent = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
    )
    due_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class ExpenseSharePreviewResultSerializer(serializers.Serializer):
    partner_id = serializers.IntegerField()
    year = serializers.IntegerField()
    month = serializers.IntegerField()
    partner_percent = serializers.DecimalField(
        max_digits=5, decimal_places=2, allow_null=True
    )
    total_expenses_usd = serializers.DecimalField(max_digits=14, decimal_places=2)
    partner_share_usd = serializers.DecimalField(max_digits=14, decimal_places=2)
    my_share_usd = serializers.DecimalField(max_digits=14, decimal_places=2)
    lines = serializers.ListField()
