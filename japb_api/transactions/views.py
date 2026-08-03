import calendar
from datetime import timedelta, datetime, date, time
from dateutil.relativedelta import relativedelta
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets, filters
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .tasks import update_reports
from ..accounts.models import Account
from japb_api.currencies.models import CurrencyConversionHistorial, Currency
from japb_api.receivables.models import Receivable
from .permissions import IsOwnerOrReadOnly, IsOwner
from .models import (
    Transaction,
    TransactionGroup,
    CurrencyExchange,
    ExchangeComission,
    Category,
)
from .serializers import (
    TransactionSerializer,
    TransactionGroupListSerializer,
    CurrencyExchangeSerializer,
    ExchangeComissionSerializer,
    CategorySerializer,
    TransactionFilterSet,
)
from japb_api.products.tasks import update_user_product_list_items
from japb_api.receivables.utils import (
    expand_contact_collection,
    get_or_create_contact,
)
from .utils import convert_transaction_to_usd, parse_amount, should_skip_transaction


def _coerce_to_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        dt = parse_datetime(value)
        if dt:
            return dt.date()
        d = parse_date(value)
        if d:
            return d
    return None


def apply_receivable_link(request, tx_data, parsed_amount, existing_transaction=None):
    """
    Resolve receivable FK and optionally create a Receivable for loans. Mutates tx_data.
    Returns a Response error or None.
    """
    if tx_data.get("receivable") not in (None, ""):
        try:
            rec = Receivable.objects.get(pk=tx_data["receivable"])
        except (Receivable.DoesNotExist, TypeError, ValueError):
            return Response(
                {"receivable": ["Invalid receivable."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if str(rec.user_id) != str(request.user.id):
            return Response(
                {"receivable": ["Invalid receivable."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tx_data["receivable"] = rec.pk
        return None

    if parsed_amount > 0 and (tx_data.get("contact") or "").strip():
        return None

    is_loan = tx_data.get("is_loan", False)
    if not is_loan:
        return None

    if parsed_amount >= 0:
        return Response(
            {"is_loan": ["Loan transactions must have a negative amount."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if existing_transaction and existing_transaction.receivable_id:
        return None

    contact = (tx_data.get("contact") or "").strip()
    if not contact:
        return Response(
            {"contact": ["This field is required when is_loan is true."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    raw_date = tx_data.get("date")
    if raw_date is None and existing_transaction is not None:
        base_date = existing_transaction.date.date()
    else:
        base_date = _coerce_to_date(raw_date)
    if base_date is None:
        return Response(
            {"date": ["A valid date is required when creating a loan receivable."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    loan_due_date = tx_data.get("loan_due_date")
    if loan_due_date:
        if isinstance(loan_due_date, datetime):
            due = loan_due_date.date()
        elif isinstance(loan_due_date, date) and not isinstance(loan_due_date, datetime):
            due = loan_due_date
        else:
            due = _coerce_to_date(loan_due_date)
            if due is None:
                return Response(
                    {"loan_due_date": ["Invalid date."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
    else:
        due = base_date + relativedelta(months=1)

    description = (tx_data.get("description") or "").strip()
    if not description and existing_transaction is not None:
        description = existing_transaction.description or ""

    contact_obj = get_or_create_contact(request.user, contact)
    rec = Receivable.objects.create(
        user=request.user,
        description=description,
        contact=contact_obj,
        due_date=due,
    )
    tx_data["receivable"] = rec.pk
    return None


apply_loan_receivable = apply_receivable_link


def _coerce_to_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if timezone.is_aware(value) else timezone.make_aware(value)
    if isinstance(value, date) and not isinstance(value, datetime):
        return timezone.make_aware(datetime.combine(value, time.min))
    if isinstance(value, str):
        dt = parse_datetime(value)
        if dt:
            return dt if timezone.is_aware(dt) else timezone.make_aware(dt)
        d = parse_date(value)
        if d:
            return timezone.make_aware(datetime.combine(d, time.min))
    return None


def _delete_group_if_empty(group):
    if group is None:
        return
    if not group.transactions.exists():
        group.delete()


def _is_transaction_pk(value):
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, str) and value.isdigit():
        return True
    return False


class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filterset_class = TransactionFilterSet
    ordering_fields = ["date"]
    ordering = ["-date"]
    permission_classes = (
        IsAuthenticated,
        IsOwner,
    )

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)

    def _create_group_from_existing_ids(self, request, data, raw_ids):
        """Bind existing transactions into a new display group."""
        try:
            ids = [int(pk) for pk in raw_ids]
        except (TypeError, ValueError):
            return Response(
                {"transactions": ["Transaction ids must be integers."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        unique_ids = list(dict.fromkeys(ids))
        transactions = list(
            Transaction.objects.filter(user=request.user, pk__in=unique_ids)
            .select_related("account", "receivable", "receivable__contact")
            .order_by("date")
        )
        if len(transactions) != len(unique_ids):
            return Response(
                {"transactions": ["One or more transactions were not found."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        group_date = _coerce_to_datetime(data.get("date"))
        if group_date is None:
            group_date = min(tx.date for tx in transactions)

        name = (data.get("name") or "").strip()
        if not name:
            name = (transactions[0].description or "").strip() or "Transaction group"

        group = TransactionGroup.objects.create(
            user=request.user,
            name=name,
            date=group_date,
        )

        previous_groups = []
        for tx in transactions:
            if tx.group_id and tx.group_id != group.id:
                previous_groups.append(tx.group)
            tx.group = group
            tx.save(update_fields=["group", "updated_at"])

        for previous in previous_groups:
            _delete_group_if_empty(previous)

        serializer = self.get_serializer(transactions, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def _normalize_create_payload(self, request):
        """
        Returns (transactions_data, new_group_or_None, error_Response_or_None).
        Supports:
        - { "group": true, "name": "...", "transactions": [ {...}, ... ] }  (create new)
        - bare list / single object (optional group_id per item)
        Existing-id grouping is handled separately in create().
        """
        data = request.data
        if isinstance(data, dict) and data.get("group") is True:
            transactions_data = data.get("transactions")
            if not isinstance(transactions_data, list) or len(transactions_data) == 0:
                return None, None, Response(
                    {"transactions": ["This field is required and must be a non-empty list."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not all(isinstance(item, dict) for item in transactions_data):
                return None, None, Response(
                    {
                        "transactions": [
                            "Expected a list of transaction objects, or a list of existing transaction ids."
                        ]
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            for item in transactions_data:
                if item.get("group_id") is not None:
                    return None, None, Response(
                        {"group_id": ["Cannot bind to an existing group when creating a new group."]},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Group date is optional on the payload. Default: oldest member transaction date.
            group_date = _coerce_to_datetime(data.get("date"))
            if group_date is None:
                dates = []
                for item in transactions_data:
                    dt = _coerce_to_datetime(item.get("date"))
                    if dt is not None:
                        dates.append(dt)
                if not dates:
                    return None, None, Response(
                        {
                            "transactions": [
                                "Each transaction needs a valid date so the group date can default to the oldest."
                            ]
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                group_date = min(dates)

            name = (data.get("name") or "").strip()
            if not name:
                first = transactions_data[0]
                name = (first.get("description") or "").strip() or "Transaction group"

            group = TransactionGroup.objects.create(
                user=request.user,
                name=name,
                date=group_date,
            )
            return transactions_data, group, None

        if not isinstance(data, list):
            return [data], None, None
        return data, None, None

    def create(self, request):
        data = request.data
        # Group existing transactions by id:
        # { "group": true, "name": "...", "transactions": [1, 2, 3] }
        if isinstance(data, dict) and data.get("group") is True:
            items = data.get("transactions")
            if isinstance(items, list) and items and all(_is_transaction_pk(i) for i in items):
                return self._create_group_from_existing_ids(request, data, items)

        transactions_data, new_group, err = self._normalize_create_payload(request)
        if err is not None:
            return err

        created_transactions = []
        for transaction_data in transactions_data:
            if not isinstance(transaction_data, dict):
                if new_group is not None:
                    new_group.delete()
                return Response(
                    {
                        "transactions": [
                            "Expected a list of transaction objects, or a list of existing transaction ids."
                        ]
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            tx_data = transaction_data.copy()

            if new_group is not None:
                tx_data.pop("group_id", None)

            account = Account.objects.get(pk=tx_data.get("account"))

            amount = float(tx_data.get("amount"))
            decimal_places = account.decimal_places

            parsed_amount = parse_amount(amount, decimal_places)
            tx_data["amount"] = parsed_amount

            conversion = (
                CurrencyConversionHistorial.objects.filter(
                    currency_from=account.currency,
                    currency_to__name="USD",
                    source=account.currency.default_conversion_source,
                    date__lte=tx_data.get("date"),
                )
                .order_by("-date")
                .first()
            )

            if conversion:
                tx_data["to_main_currency_amount"] = int(
                    parse_amount(amount, 2) / conversion.rate
                )

            split_result = expand_contact_collection(
                request, tx_data, parsed_amount, account, conversion
            )
            if isinstance(split_result, Response):
                if new_group is not None:
                    new_group.delete()
                return split_result

            batch = split_result if split_result is not None else [tx_data]

            for item in batch:
                err = apply_receivable_link(request, item, item["amount"])
                if err is not None:
                    if new_group is not None:
                        new_group.delete()
                    return err

                transaction_serializer = self.get_serializer(data=item)
                if transaction_serializer.is_valid():
                    if new_group is not None:
                        transaction = transaction_serializer.save(group=new_group)
                    else:
                        transaction = transaction_serializer.save()
                    created_transactions.append(transaction_serializer.data)

                    update_reports.delay(transaction.account.id)
                    update_user_product_list_items.delay(transaction.user.id)
                else:
                    if new_group is not None and not created_transactions:
                        new_group.delete()
                    return Response(
                        transaction_serializer.errors,
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        return Response(created_transactions, status=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        # When filtering by group, return member transactions without collapsing
        if request.query_params.get("group") not in (None, ""):
            return super().list(request, *args, **kwargs)

        queryset = self.filter_queryset(self.get_queryset())

        ungrouped = list(queryset.filter(group__isnull=True))
        group_ids = (
            queryset.filter(group__isnull=False)
            .values_list("group_id", flat=True)
            .distinct()
        )
        groups = list(
            TransactionGroup.objects.filter(
                user=request.user, id__in=group_ids
            ).prefetch_related("transactions")
        )

        feed = []
        for tx in ungrouped:
            feed.append(("transaction", tx.date, tx))
        for group in groups:
            feed.append(("group", group.date, group))

        reverse = True
        ordering = request.query_params.get("ordering", "-date")
        if ordering == "date":
            reverse = False
        feed.sort(key=lambda item: item[1] or timezone.now(), reverse=reverse)

        paginator = self.paginate_queryset([item[2] for item in feed])
        if paginator is not None:
            results = []
            for obj in paginator:
                if isinstance(obj, TransactionGroup):
                    results.append(
                        TransactionGroupListSerializer(obj, context={"request": request}).data
                    )
                else:
                    results.append(
                        self.get_serializer(obj).data
                    )
            return self.get_paginated_response(results)

        results = []
        for _, _, obj in feed:
            if isinstance(obj, TransactionGroup):
                results.append(
                    TransactionGroupListSerializer(obj, context={"request": request}).data
                )
            else:
                results.append(self.get_serializer(obj).data)
        return Response(results)

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, pk=None):
        try:
            transaction = self.get_queryset().get(pk=pk)
        except Transaction.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        previous_group = transaction.group

        tx_data = (
            request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        )

        account_id = tx_data.get("account", transaction.account_id)
        account = Account.objects.get(pk=account_id)

        if "amount" in tx_data:
            amount = float(tx_data["amount"])
        else:
            amount = transaction.amount / (10 ** transaction.account.decimal_places)

        decimal_places = account.decimal_places
        parsed_amount = parse_amount(amount, decimal_places)
        tx_data["amount"] = parsed_amount

        tx_data.setdefault("account", transaction.account_id)
        tx_data.setdefault("description", transaction.description)
        tx_data.setdefault("date", transaction.date)

        conversion = None
        if account.currency.name == "USD":
            tx_data["to_main_currency_amount"] = None
        else:
            conversion = (
                CurrencyConversionHistorial.objects.filter(
                    currency_from=account.currency,
                    currency_to__name="USD",
                    source=account.currency.default_conversion_source,
                    date__lte=tx_data.get("date"),
                )
                .order_by("-date")
                .first()
            )

            if conversion:
                tx_data["to_main_currency_amount"] = int(
                    parse_amount(amount, 2) / conversion.rate
                )

        split_result = expand_contact_collection(
            request, tx_data, parsed_amount, account, conversion
        )
        if isinstance(split_result, Response):
            return split_result
        if split_result is not None:
            return Response(
                {
                    "contact": [
                        "Contact-level collection split is only supported on create."
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        err = apply_receivable_link(
            request, tx_data, parsed_amount, existing_transaction=transaction
        )
        if err is not None:
            return err

        serializer = self.get_serializer(transaction, data=tx_data, partial=True)
        if serializer.is_valid():
            serializer.save()
            if previous_group is not None and previous_group != transaction.group:
                _delete_group_if_empty(previous_group)
            update_reports.delay(transaction.account.id)
            update_user_product_list_items.delay(transaction.user.id)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        transaction_pk = self.get_queryset().get(pk=kwargs["pk"])
        group = transaction_pk.group
        update_reports.delay(transaction_pk.account.id)
        update_user_product_list_items.delay(transaction_pk.user.id)
        response = super().destroy(request, *args, **kwargs)
        _delete_group_if_empty(group)
        return response



class CurrencyExchangeViewSet(viewsets.ModelViewSet):
    user = serializers.PrimaryKeyRelatedField(
        read_only=True, default=serializers.CurrentUserDefault()
    )
    queryset = CurrencyExchange.objects.all()
    serializer_class = CurrencyExchangeSerializer
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filterset_class = TransactionFilterSet
    ordering_fields = ["date"]
    permission_classes = (
        IsAuthenticated,
        IsOwner,
    )

    def get_queryset(self):
        return CurrencyExchange.objects.filter(user=self.request.user)

    def create(self, request):
        try:
            account_from = Account.objects.get(pk=request.data["from_account"])
            account_to = Account.objects.get(pk=request.data["to_account"])
        except Account.DoesNotExist:
            return Response(
                {"errors": {"accounts": "Invalid Accounts"}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        description = request.data.get(
            "description", f"Exchange from {account_from.name} to {account_to.name}"
        )

        from_amount = float(request.data.get("from_amount"))
        from_decimal_places = account_from.decimal_places
        request.data["from_amount"] = parse_amount(from_amount, from_decimal_places)

        to_amount = float(request.data.get("to_amount"))
        to_decimal_places = account_to.decimal_places
        request.data["to_amount"] = parse_amount(to_amount, to_decimal_places)

        # positive: comussion, negative value: profit
        comission_amount = request.data["from_amount"] - request.data["to_amount"]

        # if from_amount is greater than to_amount, its a comission debited to from_account
        # if to_amount is greater than from_amount, is a profit for to_account

        from_account_transaction_data = {
            "amount": -float(request.data["from_amount"])
            - (
                -comission_amount
                if account_from.currency == account_to.currency and comission_amount > 0
                else 0
            ),
            "account": request.data["from_account"],
            "description": description,
            "date": request.data["date"],
        }
        to_account_transaction_data = {
            "amount": float(request.data["to_amount"])
            + (
                comission_amount
                if account_from.currency == account_to.currency and comission_amount < 0
                else 0
            ),
            "account": request.data["to_account"],
            "description": description,
            "date": request.data["date"],
        }

        # check if categories "Exchanges" and "Exchanges Income exists"
        # check if categories "Exchanges" and "Exchanges Income exists"
        categories = Category.objects.filter(
            Q(user=request.user) | Q(user__isnull=True)
        )
        category_from = categories.filter(name="Exchanges").first()
        category_to = categories.filter(name="Exchanges Income").first()
        category_comission = categories.filter(name="Comissions").first()
        category_profit = categories.filter(name="Profits").first()

        if category_from:
            from_account_transaction_data["category"] = category_from.id
        if category_to:
            to_account_transaction_data["category"] = category_to.id

        # check if the from_account and to_account are the same currency
        if account_from.currency == account_to.currency:
            from_account_transaction_data["type"] = "from_same_currency"
            to_account_transaction_data["type"] = "to_same_currency"
        else:
            from_account_transaction_data["type"] = "from_different_currency"
            to_account_transaction_data["type"] = "to_different_currency"

        transaction_from_serializer = self.get_serializer(
            data=from_account_transaction_data
        )
        transaction_to_serializer = self.get_serializer(
            data=to_account_transaction_data
        )

        if transaction_from_serializer.is_valid():
            from_account_transaction = transaction_from_serializer.save()
        else:
            return Response(
                {"from_data": transaction_from_serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if transaction_to_serializer.is_valid():
            to_account_transaction = transaction_to_serializer.save()
        else:
            return Response(
                {"to_data": transaction_to_serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Set the related_transaction field of the to_account_transaction
        to_account_transaction.related_transaction = from_account_transaction
        to_account_transaction.save()

        # Set the related_transaction field of the from_account_transaction
        from_account_transaction.related_transaction = to_account_transaction
        from_account_transaction.save()

        response = [
            transaction_from_serializer.data,
            transaction_to_serializer.data,
        ]
        # Create the comission transaction
        comission_description = "Comission" if comission_amount > 0 else "Profit"

        if account_from.currency == account_to.currency and comission_amount != 0:
            comission_transaction_data = {
                "amount": -comission_amount if comission_amount > 0 else comission_amount,
                "account": request.data["from_account"]
                if comission_amount > 0
                else request.data["to_account"],
                "description": f"{comission_description} for {description}",
                "date": request.data["date"],
                "type": "comission" if comission_amount > 0 else "profit",
                "exchange_from": from_account_transaction.id,
                "exchange_to": to_account_transaction.id,
                "user": request.user.id,
            }
            if category_comission if comission_amount > 0 else category_profit:
                comission_transaction_data["category"] = (
                    category_comission if comission_amount > 0 else category_profit
                ).id

            comission_transaction_serializer = ExchangeComissionSerializer(
                data=comission_transaction_data
            )

            if comission_transaction_serializer.is_valid():
                comission_transaction_serializer.save()
                update_reports.delay(from_account_transaction.account.id)
                update_reports.delay(to_account_transaction.account.id)
                response.append(comission_transaction_serializer.data)
            else:
                return Response(
                    {"comission_data": comission_transaction_serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(response, status=status.HTTP_201_CREATED)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    ordering_fields = ["name"]
    permission_classes = (
        IsAuthenticated,
        IsOwnerOrReadOnly,
    )

    def get_queryset(self):
        """get global categories and user categories"""
        return Category.objects.filter(
            Q(user=self.request.user.id) | Q(user__isnull=True)
        )

    def create(self, request):
        categories_data = request.data
        if not isinstance(categories_data, list):
            categories_data = [categories_data]

        created_categories = []
        for category_data in categories_data:
            category_serializer = self.get_serializer(data=category_data)
            if category_serializer.is_valid():
                category_serializer.save()
                created_categories.append(category_serializer.data)
            else:
                return Response(
                    category_serializer.errors, status=status.HTTP_400_BAD_REQUEST
                )

        return Response(created_categories, status=status.HTTP_201_CREATED)

    def list(self, request):
        categories = self.filter_queryset(self.get_queryset())
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class ExpensesSummaryViewSet(viewsets.ViewSet):
    permission_classes = (IsAuthenticated,)

    def list(self, request):
        """
        Get expenses summary grouped by parent category.
        Query parameter: period (7d, 1m, current_week, current_month)
        - 7d: Last 7 days from now
        - 1m: Last 30 days from now
        - current_week: From start of current week (Monday) to now
        - current_month: From start of current month to now
        """
        period = request.query_params.get("period", "7d")
        
        # Calculate date range
        now = timezone.now()
        if period == "1m":
            from_date = now - timedelta(days=30)
        elif period == "current_week":
            # Get start of current week (Monday)
            days_since_monday = now.weekday()  # Monday is 0, Sunday is 6
            from_date = now - timedelta(days=days_since_monday)
            # Set to start of day (00:00:00)
            from_date = from_date.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "current_month":
            # Get start of current month
            from_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:  # default to 7d
            from_date = now - timedelta(days=7)
        
        to_date = now
        
        # Get all expense transactions for the user in the date range
        # Filter by expense category type if category exists
        transactions = Transaction.objects.filter(
            user=request.user,
            amount__lt=0,  # expenses only
            date__gte=from_date,
            date__lte=to_date,
        ).filter(
            Q(category__type="expense") | Q(category__isnull=True)
        ).select_related("account", "account__currency", "category", "category__parent_category")
        
        # Exclude all currency exchanges (same-currency and different-currency)
        # since amounts are always calculated as USD, exchanges should be omitted
        exchange_ids = CurrencyExchange.objects.all().values_list("id", flat=True)
        transactions = transactions.exclude(id__in=exchange_ids)
        
        # Process transactions: convert to USD and group by category
        category_totals = {}  # {parent_category_id: {id, name, total, children: {child_id: {id, name, total}}}}
        malformed_transactions = []
        usd_currency = Currency.objects.filter(name="USD").first()
        
        if not usd_currency:
            return Response(
                {"error": "USD currency not found in system"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        for transaction in transactions:
            if should_skip_transaction(transaction):
                continue

            usd_amount, error_info = convert_transaction_to_usd(transaction, usd_currency)
            if error_info:
                malformed_transactions.append(error_info)
                continue

            # Get parent category
            if transaction.category is None:
                parent_category_id = None
                parent_category_name = "Uncategorized"
                child_category_id = None
                child_category_name = None
            elif transaction.category.parent_category is None:
                # Category is a parent
                parent_category_id = transaction.category.id
                parent_category_name = transaction.category.name
                child_category_id = None
                child_category_name = None
            else:
                # Category has a parent
                parent_category_id = transaction.category.parent_category.id
                parent_category_name = transaction.category.parent_category.name
                child_category_id = transaction.category.id
                child_category_name = transaction.category.name
            
            # Initialize parent category if not exists
            if parent_category_id not in category_totals:
                category_totals[parent_category_id] = {
                    "category_id": parent_category_id,
                    "category_name": parent_category_name,
                    "total_amount_usd": 0.0,
                    "children": {},
                }
            
            # Add to parent total
            category_totals[parent_category_id]["total_amount_usd"] += abs(usd_amount)
            
            # If there's a child category, add to its total
            if child_category_id is not None:
                if child_category_id not in category_totals[parent_category_id]["children"]:
                    category_totals[parent_category_id]["children"][child_category_id] = {
                        "category_id": child_category_id,
                        "category_name": child_category_name,
                        "total_amount_usd": 0.0,
                    }
                category_totals[parent_category_id]["children"][child_category_id]["total_amount_usd"] += abs(usd_amount)
        
        # Format response
        summary = []
        for parent_id, parent_data in category_totals.items():
            children_list = list(parent_data["children"].values())
            summary.append({
                "category_id": parent_data["category_id"],
                "category_name": parent_data["category_name"],
                "total_amount_usd": round(parent_data["total_amount_usd"], 2),
                "children": children_list,
            })
        
        # Sort by total_amount_usd descending
        summary.sort(key=lambda x: x["total_amount_usd"], reverse=True)
        
        # Calculate total for the period (sum of all category totals)
        period_total = sum(category["total_amount_usd"] for category in summary)
        
        return Response({
            "period": period,
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "total": round(period_total, 2),
            "summary": summary,
            "malformed_transactions": malformed_transactions,
        })


class CashflowSummaryViewSet(viewsets.ViewSet):
    """
    Income and expense totals in USD plus net cash flow (income minus expenses).

    Query parameter: period — current_month (default), this_quarter, this_year.
    free_cash_flow_usd is net cash flow for personal finance (not corporate FCF).
    """

    permission_classes = (IsAuthenticated,)

    @staticmethod
    def _period_bounds(period, now):
        if period == "current_month":
            from_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == "this_quarter":
            quarter_start_month = ((now.month - 1) // 3) * 3 + 1
            from_date = now.replace(
                month=quarter_start_month,
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
        elif period == "this_year":
            from_date = now.replace(
                month=1, day=1, hour=0, minute=0, second=0, microsecond=0
            )
        else:
            return None
        return from_date, now

    @staticmethod
    def _accumulate_usd_totals(transactions, usd_currency, expense_mode):
        total = 0.0
        malformed_transactions = []
        for transaction in transactions:
            if should_skip_transaction(transaction):
                continue
            usd_amount, error_info = convert_transaction_to_usd(transaction, usd_currency)
            if error_info:
                malformed_transactions.append(error_info)
                continue
            if expense_mode:
                total += abs(usd_amount)
            elif usd_amount > 0:
                total += usd_amount
        return total, malformed_transactions

    def list(self, request):
        period = request.query_params.get("period", "current_month")
        bounds = self._period_bounds(period, timezone.now())
        if bounds is None:
            return Response(
                {
                    "error": "period must be one of: current_month, this_quarter, this_year",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        from_date, to_date = bounds

        exchange_ids = CurrencyExchange.objects.all().values_list("id", flat=True)
        base_qs = (
            Transaction.objects.filter(
                user=request.user,
                date__gte=from_date,
                date__lte=to_date,
            )
            .exclude(id__in=exchange_ids)
            .select_related("account", "account__currency", "category")
        )

        expenses_qs = base_qs.filter(amount__lt=0).filter(
            Q(category__type="expense") | Q(category__isnull=True)
        )
        income_qs = base_qs.filter(amount__gt=0).filter(
            Q(category__type="income") | Q(category__isnull=True)
        )

        usd_currency = Currency.objects.filter(name="USD").first()
        if not usd_currency:
            return Response(
                {"error": "USD currency not found in system"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        expense_total, malformed_expenses = self._accumulate_usd_totals(
            expenses_qs, usd_currency, expense_mode=True
        )
        income_total, malformed_income = self._accumulate_usd_totals(
            income_qs, usd_currency, expense_mode=False
        )
        malformed_transactions = malformed_expenses + malformed_income
        free_cash_flow = income_total - expense_total

        return Response(
            {
                "period": period,
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
                "income_total_usd": round(income_total, 2),
                "expense_total_usd": round(expense_total, 2),
                "free_cash_flow_usd": round(free_cash_flow, 2),
                "malformed_transactions": malformed_transactions,
            }
        )


class CategoryTrendViewSet(viewsets.ViewSet):
    permission_classes = (IsAuthenticated,)

    def list(self, request):
        category_id_str = request.query_params.get("category")
        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")
        granularity = request.query_params.get("granularity", "monthly")
        exclude_str = request.query_params.get("exclude_categories", "")
        include_str = request.query_params.get("include_categories", "")

        if not category_id_str or not start_date_str or not end_date_str:
            return Response(
                {"error": "category, start_date, and end_date are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if granularity not in ("monthly", "weekly"):
            return Response(
                {"error": "granularity must be 'monthly' or 'weekly'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_dt = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if start_dt > end_dt:
            return Response(
                {"error": "start_date must be before or equal to end_date"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            category = Category.objects.get(pk=int(category_id_str))
        except (Category.DoesNotExist, ValueError, TypeError):
            return Response(
                {"error": "Category not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Build effective category set: parent + children - excluded + included
        child_ids = set(
            Category.objects.filter(parent_category=category).values_list("id", flat=True)
        )

        if exclude_str:
            try:
                exclude_ids = {int(x.strip()) for x in exclude_str.split(",") if x.strip()}
            except ValueError:
                return Response(
                    {"error": "exclude_categories must be comma-separated integers"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            child_ids -= exclude_ids

        category_ids = {category.id} | child_ids

        if include_str:
            try:
                include_ids = [int(x.strip()) for x in include_str.split(",") if x.strip()]
            except ValueError:
                return Response(
                    {"error": "include_categories must be comma-separated integers"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            found = Category.objects.filter(pk__in=include_ids)
            if found.count() != len(set(include_ids)):
                found_ids = set(found.values_list("id", flat=True))
                missing = set(include_ids) - found_ids
                return Response(
                    {"error": f"Categories not found: {missing}"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            category_ids |= set(include_ids)

        # Query expense transactions scoped to the effective category set
        start_datetime = timezone.make_aware(datetime.combine(start_dt, time.min))
        end_datetime = timezone.make_aware(datetime.combine(end_dt, time.max))

        transactions = (
            Transaction.objects.filter(
                user=request.user,
                amount__lt=0,
                date__gte=start_datetime,
                date__lte=end_datetime,
                category__in=category_ids,
            )
            .select_related("account", "account__currency", "category")
        )

        exchange_ids = CurrencyExchange.objects.all().values_list("id", flat=True)
        transactions = transactions.exclude(id__in=exchange_ids)

        # Generate period buckets
        periods, period_map = self._generate_periods(start_dt, end_dt, granularity)

        usd_currency = Currency.objects.filter(name="USD").first()
        if not usd_currency:
            return Response(
                {"error": "USD currency not found in system"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        malformed_transactions = []

        for transaction in transactions:
            if should_skip_transaction(transaction):
                continue

            usd_amount, error_info = convert_transaction_to_usd(transaction, usd_currency)
            if error_info:
                malformed_transactions.append(error_info)
                continue

            tx_date = transaction.date.date()
            if granularity == "monthly":
                key = (tx_date.year, tx_date.month)
            else:
                key = tx_date - timedelta(days=tx_date.weekday())

            if key not in period_map:
                continue

            idx = period_map[key]
            periods[idx]["total_amount_usd"] += abs(usd_amount)

            cat_id = transaction.category_id
            if cat_id != category.id:
                if cat_id not in periods[idx]["children"]:
                    periods[idx]["children"][cat_id] = {
                        "category_id": cat_id,
                        "category_name": transaction.category.name,
                        "total_amount_usd": 0.0,
                    }
                periods[idx]["children"][cat_id]["total_amount_usd"] += abs(usd_amount)

        grand_total = 0.0
        for period in periods:
            period["total_amount_usd"] = round(period["total_amount_usd"], 2)
            children_list = sorted(
                period["children"].values(),
                key=lambda c: c["total_amount_usd"],
                reverse=True,
            )
            for child in children_list:
                child["total_amount_usd"] = round(child["total_amount_usd"], 2)
            period["children"] = children_list
            grand_total += period["total_amount_usd"]

        return Response({
            "category_id": category.id,
            "category_name": category.name,
            "start_date": start_dt.isoformat(),
            "end_date": end_dt.isoformat(),
            "granularity": granularity,
            "periods": periods,
            "grand_total_usd": round(grand_total, 2),
            "malformed_transactions": malformed_transactions,
        })

    @staticmethod
    def _generate_periods(start_dt, end_dt, granularity):
        periods = []
        period_map = {}

        if granularity == "monthly":
            current = start_dt.replace(day=1)
            idx = 0
            while current <= end_dt:
                last_day = calendar.monthrange(current.year, current.month)[1]
                p_start = max(current, start_dt)
                p_end = min(date(current.year, current.month, last_day), end_dt)
                periods.append({
                    "period_start": p_start.isoformat(),
                    "period_end": p_end.isoformat(),
                    "label": f"{current.year}-{current.month:02d}",
                    "total_amount_usd": 0.0,
                    "children": {},
                })
                period_map[(current.year, current.month)] = idx
                idx += 1
                if current.month == 12:
                    current = date(current.year + 1, 1, 1)
                else:
                    current = date(current.year, current.month + 1, 1)
        else:
            current_monday = start_dt - timedelta(days=start_dt.weekday())
            idx = 0
            while current_monday <= end_dt:
                p_start = max(current_monday, start_dt)
                p_end = min(current_monday + timedelta(days=6), end_dt)
                iso_year, iso_week, _ = current_monday.isocalendar()
                periods.append({
                    "period_start": p_start.isoformat(),
                    "period_end": p_end.isoformat(),
                    "label": f"{iso_year}-W{iso_week:02d}",
                    "total_amount_usd": 0.0,
                    "children": {},
                })
                period_map[current_monday] = idx
                idx += 1
                current_monday += timedelta(days=7)

        return periods, period_map
