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
        self.product3 = Product.objects.create(name="Product 3", cost=5.00)

        # Get dates for different periods
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        last_week = today - timedelta(days=7)
        next_week = today + timedelta(days=7)
        next_month = today + relativedelta(months=1)

        # Create an active product list (period_end in the future)
        self.current_product_list = ProductList.objects.create(
            user=self.user,
            name="Current Product List",
            period_type="MONTHLY",
            period_start=yesterday,
            period_end=next_month,
        )

        # Create product list items for current list
        self.current_list_item1 = ProductListItem.objects.create(
            user=self.user,
            product=self.product1,
            product_list=self.current_product_list,
            quantity=5,
            quantity_purchased=0,
        )

        self.current_list_item2 = ProductListItem.objects.create(
            user=self.user,
            product=self.product2,
            product_list=self.current_product_list,
            quantity=3,
            quantity_purchased=0,
        )

        # Create a second active product list with different period
        self.other_product_list = ProductList.objects.create(
            user=self.user,
            name="Other Product List",
            period_type="MONTHLY",
            period_start=last_week,
            period_end=next_week,
        )

        # Create product list items for other list
        self.other_list_item = ProductListItem.objects.create(
            user=self.user,
            product=self.product1,
            product_list=self.other_product_list,
            quantity=10,
            quantity_purchased=0,
        )

        # Create transactions in different dates
        # Transaction 1: Within current period (today)
        self.transaction1 = TransactionFactory.create(
            user=self.user,
            amount=3500,
            date=today,
        )

        # Transaction items for transaction 1
        self.transaction1_item1 = TransactionItem.objects.create(
            transaction=self.transaction1,
            product=self.product1,
            quantity=2,
            price=10.00,
        )

        self.transaction1_item2 = TransactionItem.objects.create(
            transaction=self.transaction1,
            product=self.product2,
            quantity=1,
            price=15.00,
        )

        # Transaction 2: Also within current period (yesterday)
        self.transaction2 = TransactionFactory.create(
            user=self.user,
            amount=2500,
            date=yesterday,
        )

        # Transaction items for transaction 2
        self.transaction2_item1 = TransactionItem.objects.create(
            transaction=self.transaction2,
            product=self.product1,
            quantity=1,
            price=10.00,
        )

        self.transaction2_item2 = TransactionItem.objects.create(
            transaction=self.transaction2,
            product=self.product2,
            quantity=1,
            price=15.00,
        )

    # clear all after each test
    def tearDown(self):
        Product.objects.all().delete()
        ProductList.objects.all().delete()
        ProductListItem.objects.all().delete()
        Transaction.objects.all().delete()
        TransactionItem.objects.all().delete()

    def test_update_user_product_list_items(self):
        # Run the task with only user_pk (no transaction_items_pks needed anymore)
        update_user_product_list_items(self.user.pk)

        # Refresh items from the database
        self.current_list_item1.refresh_from_db()
        self.current_list_item2.refresh_from_db()
        self.other_list_item.refresh_from_db()

        # Check that quantities were updated correctly
        # Current list item1 should have 3 purchases (2 from transaction1 + 1 from transaction2)
        self.assertEqual(self.current_list_item1.quantity_purchased, 3)

        # Current list item2 should have 2 purchases (1 from transaction1 + 1 from transaction2)
        self.assertEqual(self.current_list_item2.quantity_purchased, 2)

        # Other list item for product1 should also have 3 (same transactions, overlapping periods)
        self.assertEqual(self.other_list_item.quantity_purchased, 3)

    def test_multiple_transactions_different_periods(self):
        # Create a transaction outside the current period but in the other period
        last_month = timezone.now().date() - relativedelta(months=1)

        # This transaction is before the current list period but within the other list period
        past_transaction = TransactionFactory.create(
            user=self.user,
            amount=2000,
            date=last_month,
        )

        # Transaction item for past transaction
        TransactionItem.objects.create(
            transaction=past_transaction, product=self.product1, quantity=4, price=5.00
        )

        # Run the task
        update_user_product_list_items(self.user.pk)

        # Refresh items from the database
        self.current_list_item1.refresh_from_db()
        self.other_list_item.refresh_from_db()

        # Current list item1 should only count transactions within its period (3 items)
        self.assertEqual(self.current_list_item1.quantity_purchased, 3)

        # Other list should not include the past transaction (it's before its period start)
        self.assertEqual(self.other_list_item.quantity_purchased, 3)

    def test_no_matching_transactions(self):
        # Create a transaction with an unused product
        other_transaction = TransactionFactory.create(
            user=self.user,
            amount=1500,
            date=timezone.now().date(),
        )

        TransactionItem.objects.create(
            transaction=other_transaction,
            product=self.product3,  # Product not in any list
            quantity=3,
            price=5.00,
        )

        # Run the task
        update_user_product_list_items(self.user.pk)

        # Refresh items from the database
        self.current_list_item1.refresh_from_db()
        self.current_list_item2.refresh_from_db()

        # Check that quantities were still updated correctly from the other transactions
        self.assertEqual(self.current_list_item1.quantity_purchased, 3)
        self.assertEqual(self.current_list_item2.quantity_purchased, 2)

    def test_different_user_transactions(self):
        # Create another user
        other_user = User.objects.create_user(
            username="otheruser", email="other@example.com", password="testpass123"
        )

        # Create a transaction for the other user with the same products
        other_user_transaction = TransactionFactory.create(
            user=other_user,
            amount=2000,
            date=timezone.now().date(),
        )

        TransactionItem.objects.create(
            transaction=other_user_transaction,
            product=self.product1,
            quantity=5,
            price=10.00,
        )

        # Run the task for our original user
        update_user_product_list_items(self.user.pk)

        # Refresh items from the database
        self.current_list_item1.refresh_from_db()

        # Should only count our user's transactions (3), not the other user's (5)
        self.assertEqual(self.current_list_item1.quantity_purchased, 3)
