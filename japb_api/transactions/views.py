from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets, filters
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .tasks import update_reports
from ..accounts.models import Account
from japb_api.currencies.models import CurrencyConversionHistorial
from .permissions import IsOwnerOrReadOnly, IsOwner
from .models import Transaction, CurrencyExchange, Category
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

        comission_amount = request.data["from_amount"] - request.data["to_amount"]

        from_account_transaction_data = {
            "amount": -float(request.data["from_amount"]) - (
                -comission_amount if account_from.currency == account_to.currency else 0
            ),
            "account": request.data["from_account"],
            "description": description,
            "date": request.data["date"],
        }
        to_account_transaction_data = {
            "amount": float(request.data["to_amount"]),
            "account": request.data["to_account"],
            "description": description,
            "date": request.data["date"],
        }

        # check if categories "Exchanges" and "Exchanges Income exists"
        try:
            category_from = Category.objects.get(name="Exchanges")
            category_to = Category.objects.get(name="Exchanges Income")
            category_comission = Category.objects.get(name="Comissions")
        except Category.DoesNotExist:
            category_from = None
            category_to = None
            category_comission = None

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
        if account_from.currency == account_to.currency:
            comission_transaction_data = {
                "amount": request.data["to_amount"] - request.data["from_amount"],
                "account": request.data["from_account"],
                "description": f"Comission for {description}",
                "date": request.data["date"],
                "type": "comission"
                if request.data["from_amount"] >= request.data["to_amount"]
                else "profit",
                "exchange_from": from_account_transaction.id,
                "exchange_to": to_account_transaction.id,
                "user": request.user.id,
            }
            if category_comission:
                comission_transaction_data["category"] = category_comission.id

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
