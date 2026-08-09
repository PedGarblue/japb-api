from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction as db_transaction
from django.utils import timezone as django_timezone

from japb_api.currencies.models import Currency
from japb_api.receivables.models import Receivable
from japb_api.transactions.models import Category, CurrencyExchange, Transaction
from japb_api.transactions.utils import convert_transaction_to_usd, should_skip_transaction

from .models import ExpenseShareLine, ExpenseSharePeriod


TWOPLACES = Decimal("0.01")


def money(value):
    return Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def get_usd_currency():
    return Currency.objects.filter(name="USD").first()


def _descendants_map(categories):
    """Build parent_id -> [child, ...] from an iterable of Category objects."""
    by_parent = defaultdict(list)
    for cat in categories:
        by_parent[cat.parent_category_id].append(cat)
    return by_parent


def _collect_descendants(root_id, by_parent):
    result = set()
    stack = [root_id]
    while stack:
        current = stack.pop()
        for child in by_parent.get(current, []):
            if child.id not in result:
                result.add(child.id)
                stack.append(child.id)
    return result


def resolve_category_ids(partner):
    """
    Expand included categories to themselves + all descendants, then subtract
    exclusions (each excluded category and its descendants).
    """
    include_ids = list(partner.includes.values_list("category_id", flat=True))
    exclude_ids = list(partner.excludes.values_list("category_id", flat=True))
    if not include_ids:
        return set()

    all_categories = list(Category.objects.all().only("id", "parent_category_id"))
    by_parent = _descendants_map(all_categories)

    resolved = set()
    for cat_id in include_ids:
        resolved.add(cat_id)
        resolved |= _collect_descendants(cat_id, by_parent)

    for cat_id in exclude_ids:
        resolved.discard(cat_id)
        resolved -= _collect_descendants(cat_id, by_parent)

    return resolved


def month_date_range(year, month):
    start = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)
    last_day = monthrange(year, month)[1]
    end = datetime(year, month, last_day, 23, 59, 59, 999999, tzinfo=timezone.utc)
    return start, end


def default_due_date(year, month):
    """Last day of the month following the share period."""
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1
    last_day = monthrange(next_year, next_month)[1]
    return date(next_year, next_month, last_day)


def aggregate_partner_expenses(user, partner, year, month, partner_percent=None, usd_currency=None):
    """
    Aggregate eligible expense transactions for a partner/month in USD.
    Returns dict with total_expenses_usd, partner_share_usd, my_share_usd, lines.
    """
    if usd_currency is None:
        usd_currency = get_usd_currency()
    if usd_currency is None:
        raise ValueError("USD currency not found in system")

    category_ids = resolve_category_ids(partner)
    lines = []
    total = Decimal("0.00")

    if category_ids:
        from_date, to_date = month_date_range(year, month)
        exchange_ids = CurrencyExchange.objects.all().values_list("id", flat=True)
        transactions = (
            Transaction.objects.filter(
                user=user,
                amount__lt=0,
                date__gte=from_date,
                date__lte=to_date,
                category_id__in=category_ids,
            )
            .exclude(id__in=exchange_ids)
            .select_related("account", "account__currency", "category")
        )

        by_category = defaultdict(lambda: {"total": Decimal("0.00"), "count": 0})
        for tx in transactions:
            if should_skip_transaction(tx):
                continue
            usd_amount, error_info = convert_transaction_to_usd(tx, usd_currency)
            if error_info:
                continue
            # expenses are negative; use absolute value
            usd_abs = money(abs(usd_amount))
            by_category[tx.category_id]["total"] += usd_abs
            by_category[tx.category_id]["count"] += 1
            by_category[tx.category_id]["category"] = tx.category

        percent = (
            Decimal(str(partner_percent))
            if partner_percent is not None
            else Decimal("0")
        )
        for category_id, data in sorted(
            by_category.items(),
            key=lambda item: (
                item[1]["category"].name if item[1].get("category") else ""
            ),
        ):
            expense_total = money(data["total"])
            partner_share = money(expense_total * percent / Decimal("100"))
            lines.append(
                {
                    "category": data.get("category"),
                    "category_id": category_id,
                    "category_name": data["category"].name if data.get("category") else None,
                    "expense_total_usd": expense_total,
                    "partner_share_usd": partner_share,
                    "transaction_count": data["count"],
                }
            )
            total += expense_total

    percent = (
        Decimal(str(partner_percent)) if partner_percent is not None else Decimal("0")
    )
    total = money(total)
    partner_share_usd = money(total * percent / Decimal("100"))
    my_share_usd = money(total - partner_share_usd)

    return {
        "total_expenses_usd": total,
        "partner_share_usd": partner_share_usd,
        "my_share_usd": my_share_usd,
        "partner_percent": money(percent) if partner_percent is not None else None,
        "lines": lines,
        "year": year,
        "month": month,
    }


@db_transaction.atomic
def finalize_period(
    user,
    partner,
    year,
    month,
    partner_percent,
    due_date=None,
    notes="",
    usd_currency=None,
):
    """
    Snapshot aggregation into ExpenseSharePeriod/Lines and create or update
    a Receivable with explicit_principal_usd.
    """
    aggregation = aggregate_partner_expenses(
        user, partner, year, month, partner_percent, usd_currency
    )
    partner_percent = Decimal(str(partner_percent))

    period, _created = ExpenseSharePeriod.objects.get_or_create(
        user=user,
        partner=partner,
        year=year,
        month=month,
        defaults={"status": ExpenseSharePeriod.STATUS_DRAFT},
    )

    period.lines.all().delete()
    for line in aggregation["lines"]:
        ExpenseShareLine.objects.create(
            period=period,
            category=line["category"],
            expense_total_usd=line["expense_total_usd"],
            partner_share_usd=line["partner_share_usd"],
            transaction_count=line["transaction_count"],
        )

    period.partner_percent = partner_percent
    period.total_expenses_usd = aggregation["total_expenses_usd"]
    period.partner_share_usd = aggregation["partner_share_usd"]
    period.my_share_usd = aggregation["my_share_usd"]
    period.status = ExpenseSharePeriod.STATUS_FINALIZED
    period.finalized_at = django_timezone.now()
    if notes is not None:
        period.notes = notes

    description = f"Shared expenses {year}-{month:02d}"
    principal = aggregation["partner_share_usd"]

    if period.receivable_id:
        receivable = period.receivable
        receivable.explicit_principal_usd = principal
        receivable.description = description
        if due_date is not None:
            receivable.due_date = due_date
        receivable.save(
            update_fields=[
                "explicit_principal_usd",
                "description",
                "due_date",
                "updated_at",
            ]
        )
    else:
        receivable = Receivable.objects.create(
            user=user,
            contact=partner.contact,
            description=description,
            due_date=due_date or default_due_date(year, month),
            explicit_principal_usd=principal,
        )
        period.receivable = receivable

    period.save()
    return period, aggregation
