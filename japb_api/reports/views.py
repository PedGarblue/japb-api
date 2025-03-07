from .models import ReportAccount, ReportCurrency
from .serializers import (
    ReportAccountSerializer,
    ReportCurrencySerializer,
    ReportAccountFilterSet,
    ReportCurrencyFilterSet,
)
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status, viewsets, filters

from japb_api.core.permissions import IsOwner


class ReportAccountViewSet(viewsets.ModelViewSet):
    serializer_class = ReportAccountSerializer
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filterset_class = ReportAccountFilterSet
    ordering_fields = ["from_date"]
    permission_classes = (
        IsAuthenticated,
        IsOwner,
    )

    def get_queryset(self):
        return ReportAccount.objects.filter(user=self.request.user)

    def create(self, request):
        reports_data = request.data
        if not isinstance(reports_data, list):
            reports_data = [reports_data]

        created_reports = []
        for report_data in reports_data:
            report_serializer = self.get_serializer(data=report_data)
            if report_serializer.is_valid():
                # calculate initial balance
                report = report_serializer.save()
                report.calculate_initial_balance()\
                    .calculate_end_balance()\
                    .calculate_total_income()\
                    .calculate_total_expenses()\
                    .save()

                created_reports.append(report_serializer.data)
            else:
                return Response(
                    report_serializer.errors, status=status.HTTP_400_BAD_REQUEST
                )

        return Response(created_reports, status=status.HTTP_201_CREATED)

    def list(self, request):
        reports = self.filter_queryset(self.get_queryset())
        serializer = ReportAccountSerializer(reports, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, pk=None):
        try:
            report = self.get_queryset().get(pk=pk)
        except ReportAccount.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(report, data=request.data)

        if serializer.is_valid():
            # calculate initial balance
            report = serializer.save()
            report.calculate_initial_balance()\
                .calculate_end_balance()\
                .calculate_total_income()\
                .calculate_total_expenses()\
                .save()

            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class ReportCurrencyViewSet(viewsets.ModelViewSet):
    serializer_class = ReportCurrencySerializer
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filterset_class = ReportCurrencyFilterSet
    ordering_fields = ["from_date"]
    permission_classes = (
        IsAuthenticated,
        IsOwner,
    )

    def get_queryset(self):
        return ReportCurrency.objects.filter(user=self.request.user)

    def create(self, request):
        reports_data = request.data
        if not isinstance(reports_data, list):
            reports_data = [reports_data]

        created_reports = []
        for report_data in reports_data:
            report_serializer = self.get_serializer(data=report_data)
            if report_serializer.is_valid():
                # calculate initial balance
                report = report_serializer.save()
                report.calculate_initial_balance()\
                    .calculate_end_balance()\
                    .calculate_total_income()\
                    .calculate_total_expenses()\
                    .save()

                created_reports.append(report_serializer.data)
            else:
                return Response(
                    report_serializer.errors, status=status.HTTP_400_BAD_REQUEST
                )

        return Response(created_reports, status=status.HTTP_201_CREATED)

    def list(self, request):
        reports = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(reports, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, pk=None):
        try:
            report = self.get_queryset().get(pk=pk)
        except ReportCurrency.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(report, data=request.data)

        if serializer.is_valid():
            # calculate initial balance
            report = serializer.save()
            report.calculate_initial_balance()\
                .calculate_end_balance()\
                .calculate_total_income()\
                .calculate_total_expenses()\
                .save()

            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
