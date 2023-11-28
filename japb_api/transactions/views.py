from rest_framework import status, viewsets, filters
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from ..accounts.models import Account
from .models import Transaction, CurrencyExchange, Category
from .serializers import TransactionSerializer, CurrencyExchangeSerializer, CategorySerializer, TransactionFilterSet
    
def parse_amount(amount, decimal_places):
    return int(amount * (10 ** decimal_places))

class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filterset_class = TransactionFilterSet
    ordering_fields = ['date']
    permission_classes = (AllowAny,)

    def list(self, request):
        qs = self.filter_queryset(self.get_queryset())
        serializer = TransactionSerializer(qs, many=True)
        return Response(serializer.data)

    def create(self, request):
        transactions_data = request.data
        if not isinstance(transactions_data, list):
            transactions_data = [transactions_data]

        created_transactions = []
        for transaction_data in transactions_data:

            transaction_serializer = self.get_serializer(data=transaction_data)

            amount = float(transaction_serializer.initial_data.get('amount'))
            decimal_places = Account.objects.get(pk=transaction_serializer.initial_data.get('account')).decimal_places
            transaction_serializer.initial_data['amount'] = parse_amount(amount, decimal_places)

            if transaction_serializer.is_valid():
                transaction = transaction_serializer.save()
                created_transactions.append(transaction_serializer.data)
            else:
                return Response(transaction_serializer.errors,
                                status=status.HTTP_400_BAD_REQUEST)

        return Response(created_transactions, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
    
    def update(self, request, pk = None):
        try:
            transaction = Transaction.objects.get(pk = pk)
        except Transaction.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = TransactionSerializer(transaction, data=request.data)

        amount = float(serializer.initial_data.get('amount'))
        decimal_places = Account.objects.get(pk=serializer.initial_data.get('account')).decimal_places
        serializer.initial_data['amount'] = parse_amount(amount, decimal_places)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
    
class CurrencyExchangeViewSet(viewsets.ModelViewSet):
    queryset = CurrencyExchange.objects.all()
    serializer_class = CurrencyExchangeSerializer
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filterset_class = TransactionFilterSet
    ordering_fields = ['date']
    permission_classes = (AllowAny,)

    def create(self, request):
        try:
            account_from = Account.objects.get(pk = request.data['from_account'])
            account_to = Account.objects.get(pk = request.data['to_account']) 
        except Account.DoesNotExist:
            return Response({ 'errors': { 'accounts': 'Invalid Accounts' } }, status = status.HTTP_400_BAD_REQUEST) 

        description = request.data.get('description', f'Exchange from {account_from.name} to {account_to.name}')

        from_amount = float(request.data.get('from_amount'))
        from_decimal_places = account_from.decimal_places
        request.data['from_amount'] = parse_amount(from_amount, from_decimal_places)

        to_amount = float(request.data.get('to_amount'))
        to_decimal_places = account_to.decimal_places
        request.data['to_amount'] = parse_amount(to_amount, to_decimal_places)

        from_account_transaction_data = {
            'amount': -float(request.data['from_amount']),
            'account': request.data['from_account'],
            'description': description,
            'date': request.data['date'],
        }
        to_account_transaction_data = {
            'amount': float(request.data['to_amount']),
            'account': request.data['to_account'],
            'description': description,
            'date': request.data['date'],
        }
        # check if the from_account and to_account are the same currency
        if account_from.currency == account_to.currency:
            from_account_transaction_data['type'] = 'from_same_currency'
            to_account_transaction_data['type'] = 'to_same_currency'
        else:
            from_account_transaction_data['type'] = 'from_different_currency'
            to_account_transaction_data['type'] = 'to_different_currency'
            
        transaction_from_serializer = self.get_serializer(data = from_account_transaction_data)
        transaction_to_serializer = self.get_serializer(data = to_account_transaction_data)

        if transaction_from_serializer.is_valid() and transaction_to_serializer.is_valid():
            # Save the transactions first so we can set the related_transaction field
            from_account_transaction = transaction_from_serializer.save()
            to_account_transaction = transaction_to_serializer.save()

            # Set the related_transaction field of the to_account_transaction
            to_account_transaction.related_transaction = from_account_transaction
            to_account_transaction.save()

            # Set the related_transaction field of the from_account_transaction
            from_account_transaction.related_transaction = to_account_transaction
            from_account_transaction.save()
            return Response([transaction_from_serializer.data, transaction_to_serializer.data], status = status.HTTP_201_CREATED) 
        return Response([transaction_from_serializer.errors, transaction_to_serializer.errors], status = status.HTTP_400_BAD_REQUEST) 
    
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    ordering_fields = ['name']
    permission_classes = (AllowAny,)

    def create(self, request):
        categories_data = request.data
        if not isinstance(categories_data, list):
            categories_data = [categories_data]

        created_categories = []
        for category_data in categories_data:
            category_serializer = self.get_serializer(data=category_data)
            if category_serializer.is_valid():
                category = category_serializer.save()
                created_categories.append(category_serializer.data)
            else:
                return Response(category_serializer.errors,
                                status=status.HTTP_400_BAD_REQUEST)

        return Response(created_categories, status=status.HTTP_201_CREATED)

    def list(self, request):
        categories = self.filter_queryset(self.get_queryset())
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, pk = None):
        try:
            category = Category.objects.get(pk = pk)
        except Category.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = CategorySerializer(category, data=request.data)

        if serializer.is_valid():
            category = serializer.save()
            return Response(serializer.data)
        else:
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)
    
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
