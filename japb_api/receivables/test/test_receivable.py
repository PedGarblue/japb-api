from datetime import date
from faker import Faker
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Receivable
from japb_api.accounts.models import Account
from japb_api.currencies.models import Currency

# /receivables/ endpoints
class TestReceivableViews(APITestCase):
    def setUp(self):
        self.fake = Faker(['en-US'])
        self.currency = Currency.objects.create(name='USD')
        self.account = Account.objects.create(name='Test Account', currency=self.currency)
        self.data = {
            'description': 'Test Receivable',
            'amount_given': 10.64,
            'amount_to_receive': 13,
            'due_date': date(2022, 1, 1),
            'account': self.account.id,
            'contact': 'contact-1',
            'status': 'UNPAID',
        }
        self.data2 = {
            'description': 'Test Receivable2',
            'amount_given': 100,
            'amount_to_receive': 130,
            'due_date': date(2022, 2, 1),
            'account': self.account.id,
            'contact': 'contact-1',
            'status': 'UNPAID',
        }
        self.data3 = {
            'description': 'Test Receivable2',
            'amount_given': 30,
            'amount_to_receive': 34,
            'due_date': date(2022, 2, 1),
            'account': self.account.id,
            'contact': 'contact-2',
            'status': 'UNPAID',
        }
        self.response = self.client.post(reverse('receivables-list'), self.data, format='json')

    def test_api_create_receivable(self):
        self.assertEqual(self.response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Receivable.objects.count(), 1)
        self.assertEqual(Receivable.objects.get().description, 'Test Receivable')
        self.assertEqual(float(Receivable.objects.get().amount_given), 10.64)
        self.assertEqual(float(Receivable.objects.get().amount_to_receive), 13.00)
        self.assertEqual(float(Receivable.objects.get().amount_paid), 0.00)
        self.assertEqual(Receivable.objects.get().status, 'UNPAID')

    def test_api_create_multiple_transactions(self):
        data = [self.data, self.data2, self.data3]
        response = self.client.post(
            reverse('receivables-list'),
            data,
            format = 'json'
        )
        self.assertEqual(self.response.status_code, status.HTTP_201_CREATED)
        # 3 + the one created at setUp()
        self.assertEqual(Receivable.objects.count(), 4)

    def test_api_get_receivables(self):
        receivable = Receivable.objects.get()
        url = reverse('receivables-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Receivable.objects.count(), 1)
        self.assertEqual(response.json()[0]['description'], 'Test Receivable')
        self.assertEqual(response.json()[0]['amount_given'], '10.64')
        self.assertEqual(response.json()[0]['amount_to_receive'], '13.00')
        self.assertEqual(response.json()[0]['amount_paid'], '0.00')
        self.assertEqual(response.json()[0]['contact'], 'contact-1')
        self.assertEqual(response.json()[0]['status'], 'UNPAID')

    def test_api_get_a_receivable(self):
        receivable = Receivable.objects.get()
        response = self.client.get(reverse('receivables-detail', kwargs={'pk': receivable.id}), format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['description'], 'Test Receivable')
        self.assertEqual(response.json()['amount_given'], '10.64')
        self.assertEqual(response.json()['amount_to_receive'], '13.00')
        self.assertEqual(response.json()['amount_paid'], '0.00')
        self.assertEqual(response.json()['contact'], 'contact-1')
        self.assertEqual(response.json()['status'], 'UNPAID')
        self.assertEqual(Receivable.objects.count(), 1)

    def test_api_can_update_a_receivable(self):
        receivable = Receivable.objects.get()
        new_data = {
            "description": "New Test Receivable",
            "amount_given": 10,
            "amount_to_receive": 13.8,
            "amount_paid": 3.8,
            "due_date": date(2022, 2, 1),
            "account": self.account.id,
            'contact': 'contact-2',
            'status': 'PAID',
        }
        response = self.client.put(reverse('receivables-detail', kwargs={'pk': receivable.id}), data=new_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Receivable.objects.get().description, "New Test Receivable")
        self.assertEqual(float(Receivable.objects.get().amount_given), 10.00)
        self.assertEqual(float(Receivable.objects.get().amount_to_receive), 13.80)
        self.assertEqual(float(Receivable.objects.get().amount_paid), 3.8)
        self.assertEqual(Receivable.objects.get().contact, 'contact-2')
        self.assertEqual(Receivable.objects.get().status, 'PAID')

    def test_api_can_partially_update_a_receivable(self):
        receivable = Receivable.objects.get()
        new_data = {
            "amount_paid": 3.8,
        }
        response = self.client.patch(reverse('receivables-detail', kwargs={'pk': receivable.id}), data=new_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Receivable.objects.count(), 1)
        self.assertEqual(Receivable.objects.get().description, 'Test Receivable')
        self.assertEqual(float(Receivable.objects.get().amount_given), 10.64)
        self.assertEqual(float(Receivable.objects.get().amount_to_receive), 13.00)
        self.assertEqual(float(Receivable.objects.get().amount_paid), 3.80)
        self.assertEqual(Receivable.objects.get().contact, 'contact-1')
        self.assertEqual(Receivable.objects.get().status, 'UNPAID')

    def test_api_can_delete_a_receivable(self):
        receivable = Receivable.objects.get()
        response = self.client.delete(reverse('receivables-detail', kwargs={'pk': receivable.id}), format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Receivable.objects.count(), 0)

