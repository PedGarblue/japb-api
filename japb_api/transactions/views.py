from rest_framework import status, viewsets, filters
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from .models import Transaction, CurrencyExchange
from .serializers import TransactionSerializer, CurrencyExchangeSerializer, TransactionFilterSet
    
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
        from_account_transaction_data = {
            'amount': -float(request.data['from_amount']),
            'description': request.data['description'],
            'account': request.data['from_account'],
            'date': request.data['date'],
        }
        to_account_transaction_data = {
            'amount': float(request.data['to_amount']),
            'description': request.data['description'],
            'account': request.data['to_account'],
            'date': request.data['date'],
        }
        serializer_from = self.get_serializer(data = from_account_transaction_data)
        serializer_to = self.get_serializer(data = to_account_transaction_data)

        if (serializer_from.is_valid() and serializer_to.is_valid()):
            from_account_transaction = serializer_from.save()
            to_account_transaction =  serializer_to.save()

            # Set the related_transaction field of the to_account_transaction
            to_account_transaction.related_transaction = from_account_transaction
            to_account_transaction.save()

            # Set the related_transaction field of the from_account_transaction
            from_account_transaction.related_transaction = to_account_transaction
            from_account_transaction.save()

            return Response([serializer_from.data, serializer_to.data], status = status.HTTP_201_CREATED) 
        return Response(status = status.HTTP_400_BAD_REQUEST)
