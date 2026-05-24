from collections import defaultdict

from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from japb_api.core.permissions import IsOwner

from .models import Contact, Receivable
from .serializers import (
    ContactDetailSerializer,
    ContactSerializer,
    ReceivableSerializer,
)
from .utils import compute_contact_totals, get_usd_currency


class ContactViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ContactSerializer
    permission_classes = (IsAuthenticated, IsOwner)
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        return (
            Contact.objects.filter(user=self.request.user)
            .prefetch_related("receivables__transactions__account__currency")
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ContactDetailSerializer
        return ContactSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["usd_currency"] = get_usd_currency()
        return context


class ReceivableViewSet(viewsets.ModelViewSet):
    serializer_class = ReceivableSerializer
    permission_classes = (
        IsAuthenticated,
        IsOwner,
    )
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    ordering_fields = ["created_at"]
    ordering = ["created_at"]

    def get_queryset(self):
        return (
            Receivable.objects.filter(user=self.request.user)
            .select_related("contact", "user")
            .prefetch_related("transactions__account__currency")
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["usd_currency"] = get_usd_currency()
        return context

    def list(self, request, *args, **kwargs):
        if request.query_params.get("group_by") == "contact":
            return self._list_grouped_by_contact(request)
        return super().list(request, *args, **kwargs)

    def _list_grouped_by_contact(self, request):
        usd_currency = get_usd_currency()
        receivables = list(self.filter_queryset(self.get_queryset()))

        groups = defaultdict(list)
        for receivable in receivables:
            groups[receivable.contact_id].append(receivable)

        results = []
        for contact_id, group_receivables in groups.items():
            contact = group_receivables[0].contact
            totals = compute_contact_totals(group_receivables, usd_currency)
            results.append(
                {
                    "contact_id": contact_id,
                    "contact": contact.name,
                    **totals,
                    "receivables": ReceivableSerializer(
                        group_receivables,
                        many=True,
                        context={
                            "request": request,
                            "usd_currency": usd_currency,
                        },
                    ).data,
                }
            )

        results.sort(key=lambda g: g["contact"].lower())
        return Response(results)
