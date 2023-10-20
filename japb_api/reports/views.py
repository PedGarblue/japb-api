from django.http import JsonResponse
from .models import Report
from .serializers import ReportSerializer, ReportFilterSet
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status, viewsets

class ReportViewSet(viewsets.ModelViewSet):
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    filter_backends = (DjangoFilterBackend,)
    permission_classes = (AllowAny,)
    filterset_class = ReportFilterSet

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
                
                report.save()

                created_reports.append(report_serializer.data)
            else:
                return Response(report_serializer.errors,
                                status=status.HTTP_400_BAD_REQUEST)

        return Response(created_reports, status=status.HTTP_201_CREATED)

    def list(self, request):
        reports = self.filter_queryset(self.get_queryset())
        serializer = ReportSerializer(reports, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, pk = None):
        try:
            report = Report.objects.get(pk = pk)
        except Report.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = ReportSerializer(report, data=request.data)

        if serializer.is_valid():
            # calculate initial balance
            report = serializer.save()
            report.calculate_initial_balance()\
                .calculate_end_balance()\
                .calculate_total_income()\
                .calculate_total_expenses()\
            
            report.save()

            return Response(serializer.data)
        else:
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)
    
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)