from rest_framework import serializers
from .models import Receivable

class ReceivableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Receivable
        fields = [
            'id',
            'description',
            'amount_given',
            'amount_to_receive',
            'amount_paid',
            'status',
            'account',
            'contact',
            'due_date',
            'created_at',
            'updated_at'
        ]
    
    
