from datetime import date
from faker import Faker
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from japb_api.users.factories import UserFactory
from japb_api.transactions.models import Category
from ..models import Product

class TestProducts(APITestCase):
    def setUp(self):
        self.fake = Faker(['en-US'])
        self.user = UserFactory()
        self.token = RefreshToken.for_user(self.user)
        self.data = {
            'name': 'Test Product',
            'description': 'Test Product',
            # 'price': 10.64,
            'cost': 1300,
            # 'stock': 10,
            'status': 'ACTIVE',
        }
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token.access_token}')
        self.response_create = self.client.post(reverse('products-list'), self.data, format='json')

    def test_api_create_product(self):
        response = self.client.post(reverse('products-list'), self.data, format='json')

        product = Product.objects.get(pk=response.data['id'])
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Product.objects.count(), 2) # 1 from setUp and 1 from this test
        self.assertEqual(product.name, 'Test Product')
        self.assertEqual(product.description, 'Test Product')
        self.assertEqual(product.cost, 1300)
    
    def test_api_create_product_can_create_with_category(self):
        category = Category.objects.create(name='Test Category', description='Test Category')
        self.data['category'] = category.id
        response = self.client.post(reverse('products-list'), self.data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Product.objects.count(), 2)
        self.assertEqual(Product.objects.get(pk=response.data['id']).category.name, 'Test Category')
        

    def test_api_get_a_product(self):
        pk = self.response_create.data['id']
        response = self.client.get(reverse('products-detail', kwargs={'pk': pk }))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Product')
        self.assertEqual(response.data['description'], 'Test Product')
        self.assertEqual(response.data['cost'], '1300.00')
        self.assertEqual(response.data['status'], 'ACTIVE')

    def test_api_get_all_products(self):
        response = self.client.get(reverse('products-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_api_can_update_product(self):
        pk = self.response_create.data['id']
        response = self.client.put(reverse('products-detail', kwargs={'pk': pk }), self.data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Product')
        self.assertEqual(response.data['description'], 'Test Product')
        self.assertEqual(response.data['cost'], '1300.00')
        self.assertEqual(response.data['status'], 'ACTIVE')

    def test_api_can_delete_product(self):
        response = self.client.delete(reverse('products-detail', kwargs={'pk': 1}))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Product.objects.count(), 0)

    def test_api_can_search_products_by_name(self):
        # Create additional test products
        Product.objects.create(
            name='Orange Juice',
            description='Fresh orange juice',
            cost=250,
            user=self.user
        )
        Product.objects.create(
            name='Banana Smoothie',
            description='Contains apple juice',
            cost=350,
            user=self.user
        )

        url = reverse('products-list') + '?search=Test'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Test Product')

    def test_api_can_search_products_by_description(self):
        Product.objects.create(
            name='Smoothie',
            description='Test flavor smoothie',
            cost=350,
            user=self.user
        )

        url = reverse('products-list') + '?search=Test'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)  # Should find both products with "Test" in name or description

    def test_api_search_products_case_insensitive(self):
        url = reverse('products-list') + '?search=test'  # lowercase search
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Test Product')

    def test_api_search_products_no_results(self):
        url = reverse('products-list') + '?search=nonexistent'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)
