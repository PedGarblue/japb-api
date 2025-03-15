from django.test import TestCase
from datetime import timedelta, datetime
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from japb_api.products.models import ProductList, ProductListItem, Product
from japb_api.products.tasks import renew_product_lists, update_user_product_list_items
from japb_api.users.models import User
from japb_api.transactions.models import Transaction, TransactionItem
from japb_api.transactions.factories import TransactionFactory


class TestRenewProductLists(TestCase):
    def setUp(self):
        # Create product lists with different conditions
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)

        # Should be renewed: period ended yesterday, monthly
        self.monthly_expired = ProductList.objects.create(
            name="Monthly Expired List",
            period_type="MONTHLY",
            period_start=yesterday - timedelta(days=30),
            period_end=yesterday,
        )

        # Should be renewed: period ends today, monthly
        self.monthly_ending_today = ProductList.objects.create(
            name="Monthly Ending Today",
            period_type="MONTHLY",
            period_start=today - timedelta(days=30),
            period_end=today,
        )

        # Should NOT be renewed: period ends tomorrow, monthly
        self.monthly_future = ProductList.objects.create(
            name="Monthly Future List",
            period_type="MONTHLY",
            period_start=tomorrow - timedelta(days=30),
            period_end=tomorrow,
        )

        # Should NOT be renewed: period ended yesterday, but not monthly
        self.no_period_expired = ProductList.objects.create(
            name="No Period Expired List",
            period_type="NO_PERIOD",
            period_start=yesterday - timedelta(days=30),
            period_end=yesterday,
        )

        # Create a product and add it to one of the lists
        self.test_product = Product.objects.create(name="Test Product", cost=10.00)

        self.list_item = ProductListItem.objects.create(
            product=self.test_product,
            product_list=self.monthly_expired,
            quantity=5,
            quantity_purchased=3,
        )

    def test_renew_product_lists(self):
        today = timezone.now().date()

        # Get initial count of product lists
        initial_count = ProductList.objects.count()

        # Run the task
        renew_product_lists()

        # Refresh the objects from the database
        self.monthly_expired.refresh_from_db()
        self.monthly_ending_today.refresh_from_db()
        self.monthly_future.refresh_from_db()
        self.no_period_expired.refresh_from_db()

        # Check that original product lists remain unchanged
        self.assertEqual(self.monthly_expired.period_start, today - timedelta(days=31))
        self.assertEqual(self.monthly_expired.period_end, today - timedelta(days=1))

        self.assertEqual(
            self.monthly_ending_today.period_start, today - timedelta(days=30)
        )
        self.assertEqual(self.monthly_ending_today.period_end, today)

        # Check that new product lists were created (2 lists should be renewed)
        self.assertEqual(ProductList.objects.count(), initial_count + 2)

        # Check the duplicated lists
        # 1. Find the duplicate of monthly_expired
        duplicate_expired = ProductList.objects.get(
            name=self.monthly_expired.name, period_start=today - timedelta(days=1)
        )
        expected_end_date = (today - timedelta(days=1)) + relativedelta(months=1)
        self.assertEqual(duplicate_expired.period_end, expected_end_date)

        # 2. Find the duplicate of monthly_ending_today
        duplicate_today = ProductList.objects.get(
            name=self.monthly_ending_today.name, period_start=today
        )
        expected_end_date_today = today + relativedelta(months=1)
        self.assertEqual(duplicate_today.period_end, expected_end_date_today)

        # Check that items were duplicated
        duplicate_items = ProductListItem.objects.filter(product_list=duplicate_expired)
        self.assertEqual(duplicate_items.count(), 1)
        duplicate_item = duplicate_items.first()

        # Verify item properties
        self.assertEqual(duplicate_item.product, self.test_product)
        self.assertEqual(duplicate_item.quantity, self.list_item.quantity)
        self.assertEqual(duplicate_item.quantity_purchased, 0)  # Should be reset

    # Test with specific dates to verify month-end handling
    @freeze_time("2024-01-31")  # January 31st
    def test_month_end_handling(self):
        # Create a product list ending on January 31st
        jan_31 = datetime(2024, 1, 31).date()

        ProductList.objects.create(
            name="January List",
            period_type="MONTHLY",
            period_start=jan_31 - relativedelta(months=1),
            period_end=jan_31,
        )

        # Run the task
        renew_product_lists()

        # Find the new product list
        new_list = ProductList.objects.get(name="January List", period_start=jan_31)

        # The end date should be February 29, 2024 (leap year)
        expected_end = datetime(2024, 2, 29).date()
        self.assertEqual(new_list.period_end, expected_end)

    def test_no_product_lists_to_renew(self):
        # Clean up data from setUp to start fresh
        ProductList.objects.all().delete()

        # Test with no matching product lists
        tomorrow = timezone.now().date() + timedelta(days=1)

        # Create a product list that won't be renewed
        future_list = ProductList.objects.create(
            name="Future List",
            period_type="MONTHLY",
            period_start=tomorrow - timedelta(days=30),
            period_end=tomorrow,
        )

        initial_count = ProductList.objects.count()

        # Run the task
        renew_product_lists()

        # Verify that no new lists were created
        self.assertEqual(ProductList.objects.count(), initial_count)

        # Verify that the original list is unchanged
        future_list.refresh_from_db()
        self.assertEqual(future_list.period_end, tomorrow)


class TestUpdateUserProductListItems(TestCase):
    def setUp(self):
        # Create a user
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        # Create products
        self.product1 = Product.objects.create(name="Product 1", cost=10.00)
        self.product2 = Product.objects.create(name="Product 2", cost=15.00)

        # Create an active product list (period_end in the future)
        today = timezone.now().date()
        next_month = today + relativedelta(months=1)

        self.product_list = ProductList.objects.create(
            user=self.user,
            name="Test Product List",
            period_type="MONTHLY",
            period_start=today,
            period_end=next_month,
        )

        # Create product list items
        self.list_item1 = ProductListItem.objects.create(
            user=self.user,
            product=self.product1,
            product_list=self.product_list,
            quantity=5,
            quantity_purchased=1,  # Already purchased 1
        )

        self.list_item2 = ProductListItem.objects.create(
            user=self.user,
            product=self.product2,
            product_list=self.product_list,
            quantity=3,
            quantity_purchased=0,
        )

        # Create a transaction
        self.transaction = TransactionFactory.create(
            user=self.user,
            amount=3500,
            date=today,
        )

        # Create transaction items
        self.transaction_item1 = TransactionItem.objects.create(
            transaction=self.transaction, product=self.product1, quantity=1, price=10.00
        )

        self.transaction_item2 = TransactionItem.objects.create(
            transaction=self.transaction, product=self.product2, quantity=2, price=15.00
        )

    def test_update_user_product_list_items(self):
        # Run the task
        transaction_items_pks = [self.transaction_item1.pk, self.transaction_item2.pk]
        update_user_product_list_items(self.user.pk, transaction_items_pks)

        # Refresh items from the database
        self.list_item1.refresh_from_db()
        self.list_item2.refresh_from_db()

        # Check that quantities were updated correctly
        # list_item1 had quantity_purchased=1, should now be 2 (1+1)
        self.assertEqual(self.list_item1.quantity_purchased, 2)

        # list_item2 had quantity_purchased=0, should now be 2 (0+2)
        self.assertEqual(self.list_item2.quantity_purchased, 2)

    def test_multiple_transaction_items_same_product(self):
        # Create additional transaction items for the same product
        transaction_item3 = TransactionItem.objects.create(
            transaction=self.transaction, product=self.product1, quantity=2, price=10.00
        )

        # Run the task with all transaction items
        transaction_items_pks = [
            self.transaction_item1.pk,
            self.transaction_item2.pk,
            transaction_item3.pk,
        ]
        update_user_product_list_items(self.user.pk, transaction_items_pks)

        # Refresh items from the database
        self.list_item1.refresh_from_db()
        self.list_item2.refresh_from_db()

        # Check that quantities were updated correctly
        # list_item1 had quantity_purchased=1, should now be 4 (1+1+2)
        self.assertEqual(self.list_item1.quantity_purchased, 4)

        # list_item2 had quantity_purchased=0, should now be 2 (0+2)
        self.assertEqual(self.list_item2.quantity_purchased, 2)

    def test_no_matching_transactions(self):
        # Create a different product not in the product list
        product3 = Product.objects.create(name="Product 3", cost=5.00)

        # Create transaction item for the new product
        transaction_item3 = TransactionItem.objects.create(
            transaction=self.transaction, product=product3, quantity=3, price=5.00
        )

        # Run the task with only this transaction item
        update_user_product_list_items(self.user.pk, [transaction_item3.pk])

        # Refresh items from the database
        self.list_item1.refresh_from_db()
        self.list_item2.refresh_from_db()

        # Check that quantities were not changed since the product doesn't match
        self.assertEqual(self.list_item1.quantity_purchased, 1)
        self.assertEqual(self.list_item2.quantity_purchased, 0)
