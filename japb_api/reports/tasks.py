import datetime
import calendar
from datetime import datetime, timedelta
import calendar
from django.utils import timezone

from japb_api.users.models import User
from japb_api.reports.models import ReportAccount, ReportCurrency
from japb_api.accounts.models import Account
from japb_api.currencies.models import Currency
from japb_api.transactions.models import Transaction, CurrencyExchange
from japb_api.celery import app

def get_last_n_months(n = 12):
    today = datetime.today()
    result = []
    
    # Loop through the last 12 months
    for i in range(n):
        # Calculate the first day of the month
        first_day = (today.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
        # Calculate the last day of the month
        last_day = first_day.replace(day=calendar.monthrange(first_day.year, first_day.month)[1])
        result.append([first_day, last_day])

    return result

def update_reports_of_account(account):
    month_ranges = get_last_n_months(48)

    for month_range in month_ranges:
        from_date = month_range[0]
        to_date = month_range[1]
        
        # check existing report
        report_account = ReportAccount.objects.filter(user=account.user, account=account, from_date=from_date, to_date=to_date)
        if not report_account.exists():
            report_account = ReportAccount.objects.create(
                user = account.user,
                account = account,
                from_date = from_date,
                to_date = to_date
            )
        else:
            # check for duplicated reports
            if report_account.count() > 1:
                report_account.exclude(pk=report_account.first().pk).delete()
            report_account = report_account.first()

        report_account.calculate_initial_balance()\
            .calculate_end_balance()\
            .calculate_total_income()\
            .calculate_total_expenses()\
            .save()

def update_reports_of_currency(currency, user):
    month_ranges = get_last_n_months(48)

    for month_range in month_ranges:
        from_date = month_range[0]
        to_date = month_range[1]
        
        report_currency = ReportCurrency.objects.filter(user=user, currency=currency, from_date=from_date, to_date=to_date)
        if not report_currency.exists():
            report_currency = ReportCurrency.objects.create(
                user = user,
                currency = currency,
                from_date = from_date,
                to_date = to_date
            )
        else:
            # check for duplicated reports
            if report_currency.count() > 1:
                report_currency.exclude(pk=report_currency.first().pk).delete()
            report_currency = report_currency.first()

        report_currency.calculate_initial_balance()\
            .calculate_end_balance()\
            .calculate_total_income()\
            .calculate_total_expenses()\
            .save()

def update_account_reports():
    accounts = Account.objects.all()

    for account in accounts:
        update_reports_of_account(account)
    
def update_currency_reports():
    users = User.objects.all()
    currencies = Currency.objects.all()

    for user in users:
        for currency in currencies:
            update_reports_of_currency(currency, user)

@app.task
def update_user_reports():
    update_account_reports()
    update_currency_reports()
    return 'Reports updated successfully'