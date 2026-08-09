from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from japb_api.core.permissions import IsOwner

from .models import ExpenseSharePartner, ExpenseSharePeriod
from .serializers import (
    ExpenseShareFinalizeSerializer,
    ExpenseSharePartnerSerializer,
    ExpenseSharePeriodSerializer,
    ExpenseSharePreviewSerializer,
)
from .utils import aggregate_partner_expenses, finalize_period, get_usd_currency


class ExpenseSharePartnerViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseSharePartnerSerializer
    permission_classes = (IsAuthenticated, IsOwner)
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filterset_fields = ["is_active"]
    ordering_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return (
            ExpenseSharePartner.objects.filter(user=self.request.user)
            .select_related("contact", "user")
            .prefetch_related("includes", "excludes")
        )


class ExpenseSharePeriodViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ExpenseSharePeriodSerializer
    permission_classes = (IsAuthenticated, IsOwner)
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filterset_fields = ["year", "month", "partner", "status"]
    ordering_fields = ["year", "month", "finalized_at", "created_at"]
    ordering = ["-year", "-month"]

    def get_queryset(self):
        return (
            ExpenseSharePeriod.objects.filter(user=self.request.user)
            .select_related("partner", "partner__contact", "receivable", "user")
            .prefetch_related("lines__category")
        )

    def _get_owned_partner(self, partner_id):
        return ExpenseSharePartner.objects.filter(
            user=self.request.user, pk=partner_id
        ).first()

    @action(detail=False, methods=["get"], url_path="preview")
    def preview(self, request):
        serializer = ExpenseSharePreviewSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        partner = self._get_owned_partner(data["partner"])
        if partner is None:
            return Response(
                {"partner": ["Unknown partner."]},
                status=status.HTTP_404_NOT_FOUND,
            )

        partner_percent = data.get("partner_percent")
        if partner_percent is None and partner.default_partner_percent is not None:
            partner_percent = partner.default_partner_percent

        try:
            aggregation = aggregate_partner_expenses(
                request.user,
                partner,
                data["year"],
                data["month"],
                partner_percent=partner_percent,
                usd_currency=get_usd_currency(),
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        lines = [
            {
                "category_id": line["category_id"],
                "category_name": line["category_name"],
                "expense_total_usd": line["expense_total_usd"],
                "partner_share_usd": line["partner_share_usd"],
                "transaction_count": line["transaction_count"],
            }
            for line in aggregation["lines"]
        ]
        return Response(
            {
                "partner_id": partner.id,
                "year": aggregation["year"],
                "month": aggregation["month"],
                "partner_percent": aggregation["partner_percent"],
                "total_expenses_usd": aggregation["total_expenses_usd"],
                "partner_share_usd": aggregation["partner_share_usd"],
                "my_share_usd": aggregation["my_share_usd"],
                "lines": lines,
            }
        )

    @action(detail=False, methods=["post"], url_path="finalize")
    def finalize(self, request):
        serializer = ExpenseShareFinalizeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        partner = self._get_owned_partner(data["partner"])
        if partner is None:
            return Response(
                {"partner": ["Unknown partner."]},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            period, _aggregation = finalize_period(
                user=request.user,
                partner=partner,
                year=data["year"],
                month=data["month"],
                partner_percent=data["partner_percent"],
                due_date=data.get("due_date"),
                notes=data.get("notes", ""),
                usd_currency=get_usd_currency(),
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        period = (
            ExpenseSharePeriod.objects.filter(pk=period.pk)
            .select_related("partner", "partner__contact", "receivable")
            .prefetch_related("lines__category")
            .get()
        )
        return Response(
            ExpenseSharePeriodSerializer(period).data,
            status=status.HTTP_200_OK,
        )
