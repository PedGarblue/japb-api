from django.db.models import Sum
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from .models import Account
from japb_api.transactions.models import Transaction
from .serializers import AccountSerializer

class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    permission_classes = (AllowAny,)

    def list(self, request):
        accounts = self.get_queryset()
        serializer = AccountSerializer(accounts, many=True)
        return Response(serializer.data)

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request, pk=None):
        try:
            account = Account.objects.get(pk=pk)
        except Account.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = AccountSerializer(account)
        return Response(serializer.data)

    def update(self, request, pk=None):
        try:
            account = Account.objects.get(pk=pk)
        except Account.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = AccountSerializer(account, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk=None):
        try:
            account = Account.objects.get(pk=pk)
        except Account.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        account.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class AccountsBalanceViewSet(viewsets.ViewSet):
    permission_classes = (AllowAny,)
    def list(self, request):
        balances = {}
        accounts = Account.objects.values('id', 'name')
        for account in accounts:
            queryset = Transaction.objects.filter(account = account['id'])
            total = queryset.aggregate(balance=Sum('amount', default = 0))['balance']
            # classic problem of floating points in python :^)
            balances[account['name']] = "%.2f" % total
        return Response(balances, status=status.HTTP_200_OK)