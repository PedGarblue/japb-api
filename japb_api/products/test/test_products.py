from datetime import date
from faker import Faker
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Product

class TestProducts(APITestCase):
    def setUp(self):
        self.fake = Faker(['en-US'])
        self.data = {
            'name': 'Test Product',
            'description': 'Test Product',
            # 'price': 10.64,
            'cost': 1300,
            # 'stock': 10,
            'status': 'ACTIVE',
        }
        self.client.post(reverse('products-list'), self.data, format='json')

    def test_api_create_product(self):
        response = self.client.post(reverse('products-list'), self.data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(Product.objects.get().name, 'Test Product')
        self.assertEqual(Product.objects.get().description, 'Test Product')
        self.assertEqual(Product.objects.get().cost, 1300)

    def test_api_get_a_product(self):
        response = self.client.get(reverse('products-detail', kwargs={'pk': 1}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Product')
        self.assertEqual(response.data['description'], 'Test Product')
        self.assertEqual(response.data['cost'], 1300)
        self.assertEqual(response.data['status'], 'ACTIVE')

    def test_api_get_all_products(self):
        response = self.client.get(reverse('products-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_api_can_update_product(self):
        response = self.client.put(reverse('products-detail', kwargs={'pk': 1}), self.data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Product')
        self.assertEqual(response.data['description'], 'Test Product')
        self.assertEqual(response.data['cost'], 1300)
        self.assertEqual(response.data['status'], 'ACTIVE')

    def test_api_can_delete_product(self):
        response = self.client.delete(reverse('products-detail', kwargs={'pk': 1}))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Product.objects.count(), 0)
