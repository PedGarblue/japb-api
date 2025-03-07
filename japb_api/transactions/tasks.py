from celery import shared_task

from japb_api.reports.models import ReportAccount, ReportCurrency
from japb_api.accounts.models import Account


@shared_task
def update_reports(account_pk):
    account = Account.objects.get(pk=account_pk)
    print(f"Updating reports for account {account.name} for user {account.user.pk}")
    # get most recent report
    report = (
        ReportAccount.objects.filter(user=account.user, account=account)
        .order_by("-to_date")
        .first()
    )
    report.calculate_initial_balance()\
        .calculate_end_balance()\
        .calculate_total_income()\
        .calculate_total_expenses()\
        .save()

    # get most recent report
    currency_report = (
        ReportCurrency.objects.filter(user=account.user, currency=account.currency)
        .order_by("-to_date")
        .first()
    )

    currency_report.calculate_initial_balance()\
        .calculate_end_balance()\
        .calculate_total_income()\
        .calculate_total_expenses()\
        .save()

    print("Reports updated")
