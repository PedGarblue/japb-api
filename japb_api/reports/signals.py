from django.db.models.signals import post_save
from django.dispatch import receiver
from japb_api.transactions.models import Transaction
from japb_api.reports.models import ReportAccount, ReportCurrency
from japb_api.reports.serializers import ReportAccountSerializer, ReportCurrencySerializer


@receiver(post_save, sender=Transaction)
def update_reports(sender, instance, created, **kwargs):
    # update last available account report
    account_report = ReportAccount.objects.filter(account=instance.account).last()
    account_report.calculate_initial_balance()\
        .calculate_end_balance()\
        .calculate_total_income()\
        .calculate_total_expenses()\
        .save()

    # update last available currency report
    currency_report = ReportCurrency.objects.filter(currency=instance.account.currency).last()
    currency_report.calculate_initial_balance()\
        .calculate_end_balance()\
        .calculate_total_income()\
        .calculate_total_expenses()\
        .save()
    