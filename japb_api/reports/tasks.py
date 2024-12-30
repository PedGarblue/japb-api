from japb_api.reports.models import ReportAccount, ReportCurrency
from japb_api.celery import app

@app.task()
def delete_duplicated_reports():
    reports = ReportAccount.objects.all()
    for report in reports:
        if ReportAccount.objects.filter(user=report.user, from_date=report.from_date, to_date=report.to_date).count() > 1:
            report.delete()

    reports_currency = ReportCurrency.objects.all()
    for report in reports_currency:
        if ReportCurrency.objects.filter(user=report.user, from_date=report.from_date, to_date=report.to_date).count() > 1:
            report.delete()
