from faker import Faker
from nose.tools import ok_, eq_
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Currency

class TestCurrencyViews(APITestCase):
    def setUp(self):
        self.fake = Faker(['en-US'])
        self.data = {
            'name': 'USD',
        }
        self.response = self.client.post(
            reverse('currencies-list'),
            self.data,
            format = 'json'
        )

    def test_api_create_currency(self):
        eq_(self.response.status_code, status.HTTP_201_CREATED)
        eq_(Currency.objects.count(), 1)
        self.assertEqual(Currency.objects.get().name, 'USD')

    def test_api_get_currency_list(self):
        url = reverse('currencies-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Currency.objects.count(), 1)
        self.assertEqual(response.json()[0]['name'], 'USD')

    def test_api_get_a_currency(self):
        currency = Currency.objects.get()

        response = self.client.get(reverse('currencies-detail', kwargs={ 'pk': currency.id }), format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['name'], 'USD')
        self.assertEqual(Currency.objects.count(), 1)


    def test_api_can_update_a_currency(self):
        currency = Currency.objects.get()
        new_data = {
            "name": "Super USD",
        }
        response = self.client.put(reverse('currencies-detail', kwargs={ 'pk': currency.id }), data=new_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Currency.objects.get().name, "Super USD")

    def test_api_can_delete_a_currency(self):
        currency = Currency.objects.get()
        response = self.client.delete(reverse('currencies-detail', kwargs={ 'pk': currency.id }), format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Currency.objects.count(), 0)