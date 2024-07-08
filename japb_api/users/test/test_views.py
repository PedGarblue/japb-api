from rest_framework_simplejwt.tokens import RefreshToken
from django.urls import reverse
from django.contrib.auth.hashers import check_password
from nose.tools import ok_, eq_
from rest_framework.test import APITestCase
from rest_framework import status
from faker import Faker
import factory
from ..models import User
from .factories import UserFactory

fake = Faker()


class TestLoggedUserViewSetTestCase(APITestCase):
    """
    Tests /user/me and /user/update_me endpoints.
    """

    def setUp(self):
        self.url = reverse('user-me')
        self.user = UserFactory()
        self.token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token.access_token}')

    def test_get_request_returns_logged_user(self):
        response = self.client.get(self.url)
        eq_(response.status_code, status.HTTP_200_OK)
        eq_(response.data.get('id'), self.user.id)

    def test_patch_request_updates_logged_user(self):
        new_first_name = fake.first_name()
        payload = {'first_name': new_first_name}
        response = self.client.patch(reverse('user-update-me'), payload)
        eq_(response.status_code, status.HTTP_200_OK)

        user = User.objects.get(pk=self.user.id)
        eq_(user.first_name, new_first_name)

    

class TestUserListTestCase(APITestCase):
    """
    Tests /users list operations.
    (only POST is allowed for this endpoint)
    """

    def setUp(self):
        self.url = reverse('user-list')
        self.user_data = factory.build(dict, FACTORY_CLASS=UserFactory)

    def test_post_request_with_no_data_fails(self):
        response = self.client.post(self.url, {})
        eq_(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_request_with_valid_data_succeeds(self):
        response = self.client.post(self.url, self.user_data)
        eq_(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(pk=response.data.get('id'))
        eq_(user.username, self.user_data.get('username'))
        ok_(check_password(self.user_data.get('password'), user.password))


class TestUserDetailTestCase(APITestCase):
    """
    Tests /users detail operations.
    Only the owner of the user or an admin user can access this endpoint.
    """

    def setUp(self):
        self.user = UserFactory(password='69rHb9vy123c')
        self.url = reverse('user-detail', kwargs={'pk': self.user.pk})

        # get jwt token
        self.token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token.access_token}')


    def test_get_request_returns_a_given_user(self):
        response = self.client.get(self.url)
        eq_(response.status_code, status.HTTP_200_OK)
    
    def test_get_request_returns_401_unauthorized_if_not_authenticated(self):
        self.client.credentials()
        response = self.client.get(self.url)
        eq_(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_get_request_returns_403_forbidden_if_not_owner(self):
        user = UserFactory()
        url = reverse('user-detail', kwargs={'pk': user.pk})
        response = self.client.get(url)
        eq_(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_put_request_updates_a_user(self):
        new_first_name = fake.first_name()
        payload = {'first_name': new_first_name}
        response = self.client.put(self.url, payload)
        eq_(response.status_code, status.HTTP_200_OK)

        user = User.objects.get(pk=self.user.id)
        eq_(user.first_name, new_first_name)

    def test_put_request_returns_401_unauthorized(self):
        self.client.credentials()
        new_first_name = fake.first_name()
        payload = {'first_name': new_first_name}
        response = self.client.put(self.url, payload)
        eq_(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_put_request_returns_403_forbidden(self):
        user = UserFactory()
        url = reverse('user-detail', kwargs={'pk': user.pk})
        response = self.client.get(url)
        eq_(response.status_code, status.HTTP_403_FORBIDDEN)
