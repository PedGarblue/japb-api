from datetime import timedelta, datetime
from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets, filters
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .tasks import update_reports
from ..accounts.models import Account
from japb_api.currencies.models import CurrencyConversionHistorial, Currency
from .permissions import IsOwnerOrReadOnly, IsOwner
from .models import Transaction, CurrencyExchange, ExchangeComission, Category
from .serializers import (
    TransactionSerializer,
    CurrencyExchangeSerializer,
    ExchangeComissionSerializer,
    CategorySerializer,
    TransactionFilterSet,
)
from japb_api.products.tasks import update_user_product_list_items

def parse_amount(amount, decimal_places):
    return int(amount * (10**decimal_places))


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

    def create(self, request):
        transactions_data = request.data
        if not isinstance(transactions_data, list):
            transactions_data = [transactions_data]

        created_transactions = []
        for transaction_data in transactions_data:
            transaction_serializer = self.get_serializer(data=transaction_data)
            account = Account.objects.get(
                pk=transaction_serializer.initial_data.get("account")
            )

            amount = float(transaction_serializer.initial_data.get("amount"))
            decimal_places = account.decimal_places

            transaction_serializer.initial_data["amount"] = parse_amount(
                amount, decimal_places
            )

            # Get conversion for the transaction date
            conversion = (
                CurrencyConversionHistorial.objects.filter(
                    currency_from=account.currency,
                    currency_to__name="USD",
                    source=account.currency.default_conversion_source,
                    date__lte=transaction_serializer.initial_data.get("date"),
                )
                .order_by("-date")
                .first()
            )

            if conversion:
                transaction_serializer.initial_data["to_main_currency_amount"] = int(
                    parse_amount(amount, 2) / conversion.rate
                )

            if transaction_serializer.is_valid():
                transaction = transaction_serializer.save()
                created_transactions.append(transaction_serializer.data)

                update_reports.delay(transaction.account.id)
                update_user_product_list_items.delay(transaction.user.id)
            else:
                return Response(
                    transaction_serializer.errors, status=status.HTTP_400_BAD_REQUEST
                )

        return Response(created_transactions, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, pk=None):
        try:
            transaction = self.get_queryset().get(pk=pk)
        except Transaction.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(transaction, data=request.data, partial=True)

        amount = float(serializer.initial_data.get("amount"))
        decimal_places = Account.objects.get(
            pk=serializer.initial_data.get("account")
        ).decimal_places
        serializer.initial_data["amount"] = parse_amount(amount, decimal_places)
        account = Account.objects.get(pk=serializer.initial_data.get("account"))

        if account.currency.name == "USD":
            serializer.initial_data["to_main_currency_amount"] = None

        # Get conversion for the transaction date
        conversion = (
            CurrencyConversionHistorial.objects.filter(
                currency_from=account.currency,
                currency_to__name="USD",
                source=account.currency.default_conversion_source,
                date__lte=serializer.initial_data.get("date"),
            )
            .order_by("-date")
            .first()
        )

        if conversion:
            serializer.initial_data["to_main_currency_amount"] = int(
                parse_amount(amount, 2) / conversion.rate
            )

        if serializer.is_valid():
            serializer.save()
            update_reports.delay(transaction.account.id)
            update_user_product_list_items.delay(transaction.user.id)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        transaction_pk = self.get_queryset().get(pk=kwargs["pk"])
        update_reports.delay(transaction_pk.account.id)
        update_user_product_list_items.delay(transaction_pk.user.id)
        return super().destroy(request, *args, **kwargs)


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
        
        # Exclude same-currency exchanges (but keep commissions which are separate)
        same_currency_exchange_ids = CurrencyExchange.objects.filter(
            type__in=["from_same_currency", "to_same_currency"]
        ).values_list("id", flat=True)
        transactions = transactions.exclude(id__in=same_currency_exchange_ids)
        
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
            # Check if it's a commission (should be included)
            is_commission = False
            try:
                commission = transaction.exchangecomission
                if commission.type != "comission":
                    continue  # Skip profits
                is_commission = True
            except ExchangeComission.DoesNotExist:
                pass
            
            # Skip if it's a same-currency exchange (double check)
            try:
                exchange = transaction.currencyexchange
                if exchange.type in ["from_same_currency", "to_same_currency"]:
                    continue
            except CurrencyExchange.DoesNotExist:
                pass
            
            # Convert to USD
            usd_amount = None
            
            if transaction.account.currency.name == "USD":
                # Direct conversion from integer to float
                usd_amount = transaction.amount / (10 ** transaction.account.decimal_places)
            elif transaction.to_main_currency_amount is not None:
                # Use pre-calculated USD amount (stored as integer with 2 decimal places)
                usd_amount = transaction.to_main_currency_amount / 100.0
            else:
                # Attempt conversion using CurrencyConversionHistorial
                conversion = (
                    CurrencyConversionHistorial.objects.filter(
                        currency_from=transaction.account.currency,
                        currency_to=usd_currency,
                        source=transaction.account.currency.default_conversion_source,
                        date__lte=transaction.date,
                    )
                    .order_by("-date")
                    .first()
                )
                
                if conversion:
                    # Convert: amount / (10**decimal_places) / conversion.rate
                    amount_float = transaction.amount / (10 ** transaction.account.decimal_places)
                    usd_amount = amount_float / conversion.rate
                else:
                    # No conversion available - add to malformed
                    malformed_transactions.append({
                        "id": transaction.id,
                        "description": transaction.description,
                        "date": transaction.date.isoformat(),
                        "amount": transaction.amount / (10 ** transaction.account.decimal_places),
                        "currency": transaction.account.currency.name,
                        "reason": "No conversion rate available",
                    })
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
        
        return Response({
            "period": period,
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "summary": summary,
            "malformed_transactions": malformed_transactions,
        })
