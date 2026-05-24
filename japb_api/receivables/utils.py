from japb_api.currencies.models import Currency
from japb_api.transactions.utils import convert_transaction_to_usd

from .models import Contact, Receivable


def get_usd_currency():
    return Currency.objects.filter(name="USD").first()


def compute_receivable_totals(receivable, usd_currency=None):
    if usd_currency is None:
        usd_currency = get_usd_currency()

    txs = list(
        receivable.transactions.select_related("account", "account__currency").order_by(
            "date"
        )
    )

    principal_usd = 0.0
    paid_usd = 0.0
    for tx in txs:
        usd, err = convert_transaction_to_usd(tx, usd_currency)
        if err:
            continue
        if tx.amount < 0:
            principal_usd += abs(usd)
        elif tx.amount > 0:
            paid_usd += usd

    outstanding_usd = principal_usd - paid_usd
    return {
        "principal_usd": round(principal_usd, 2),
        "paid_usd": round(paid_usd, 2),
        "outstanding_usd": round(outstanding_usd, 2),
        "status": "PAID" if outstanding_usd <= 0 else "UNPAID",
    }


def compute_contact_totals(receivables, usd_currency=None):
    if usd_currency is None:
        usd_currency = get_usd_currency()

    total_principal = 0.0
    total_paid = 0.0
    for receivable in receivables:
        totals = compute_receivable_totals(receivable, usd_currency)
        total_principal += totals["principal_usd"]
        total_paid += totals["paid_usd"]

    total_outstanding = total_principal - total_paid
    return {
        "total_principal_usd": round(total_principal, 2),
        "total_paid_usd": round(total_paid, 2),
        "total_outstanding_usd": round(total_outstanding, 2),
    }


def receivables_with_outstanding(user, contact, usd_currency=None):
    if usd_currency is None:
        usd_currency = get_usd_currency()

    receivables = (
        Receivable.objects.filter(user=user, contact=contact)
        .prefetch_related("transactions__account__currency")
        .order_by("due_date", "created_at")
    )

    open_receivables = []
    for receivable in receivables:
        totals = compute_receivable_totals(receivable, usd_currency)
        if totals["outstanding_usd"] > 0:
            open_receivables.append((receivable, totals["outstanding_usd"]))

    return open_receivables


def get_or_create_contact(user, name):
    name = (name or "").strip()
    if not name:
        raise ValueError("Contact name is required.")
    contact, _ = Contact.objects.get_or_create(user=user, name=name)
    return contact


def resolve_contact_by_name(user, name):
    name = (name or "").strip()
    if not name:
        return None
    return Contact.objects.filter(user=user, name=name).first()


def payment_usd_amount(parsed_amount, account, conversion=None, to_main_currency_amount=None):
    """Convert a parsed minor-unit amount to USD float for allocation."""
    account_float = parsed_amount / (10 ** account.decimal_places)
    if account.currency.name == "USD":
        return abs(account_float)
    if to_main_currency_amount is not None:
        return abs(to_main_currency_amount) / 100.0
    if conversion:
        return abs(account_float) / conversion.rate
    return None


def usd_to_account_minor(usd_amount, account, conversion=None):
    """Convert a USD slice to positive account minor units."""
    from japb_api.transactions.utils import parse_amount

    if account.currency.name == "USD":
        return parse_amount(usd_amount, account.decimal_places)
    if conversion:
        account_float = usd_amount * conversion.rate
        return parse_amount(account_float, account.decimal_places)
    return parse_amount(usd_amount, account.decimal_places)


def slice_to_main_currency_amount(usd_amount):
    return int(round(usd_amount * 100))


def expand_contact_collection(request, tx_data, parsed_amount, account, conversion):
    """
    Split a positive collection across open receivables (FIFO).
    Returns list of tx_data dicts, None if not applicable, or Response on error.
    """
    from rest_framework import status
    from rest_framework.response import Response

    if parsed_amount <= 0:
        return None
    if tx_data.get("receivable") not in (None, ""):
        return None

    contact_name = (tx_data.get("contact") or "").strip()
    if not contact_name:
        return None

    contact = resolve_contact_by_name(request.user, contact_name)
    if contact is None:
        return Response(
            {"contact": ["Unknown contact."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    usd_currency = get_usd_currency()
    open_receivables = receivables_with_outstanding(
        request.user, contact, usd_currency
    )
    if not open_receivables:
        return Response(
            {"contact": ["No open receivables for this contact."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    payment_usd = payment_usd_amount(
        parsed_amount,
        account,
        conversion,
        tx_data.get("to_main_currency_amount"),
    )
    if payment_usd is None:
        return Response(
            {"contact": ["No conversion rate available for this collection."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    remaining_usd = payment_usd
    splits = []
    for receivable, outstanding_usd in open_receivables:
        if remaining_usd <= 0:
            break
        slice_usd = min(remaining_usd, outstanding_usd)
        remaining_usd -= slice_usd
        split = dict(tx_data)
        split.pop("is_loan", None)
        split.pop("loan_due_date", None)
        split["contact"] = contact_name
        split["receivable"] = receivable.pk
        split["amount"] = usd_to_account_minor(slice_usd, account, conversion)
        if account.currency.name != "USD" and conversion:
            split["to_main_currency_amount"] = slice_to_main_currency_amount(slice_usd)
        elif account.currency.name == "USD":
            split["to_main_currency_amount"] = None
        splits.append(split)

    if remaining_usd > 0:
        if splits:
            last = splits[-1]
            extra_minor = usd_to_account_minor(remaining_usd, account, conversion)
            last["amount"] = last["amount"] + extra_minor
            if account.currency.name != "USD" and conversion:
                extra_main = slice_to_main_currency_amount(remaining_usd)
                last["to_main_currency_amount"] = (
                    (last.get("to_main_currency_amount") or 0) + extra_main
                )
        else:
            split = dict(tx_data)
            split["receivable"] = open_receivables[-1][0].pk
            split["amount"] = usd_to_account_minor(payment_usd, account, conversion)
            splits.append(split)

    return splits
