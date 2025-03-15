from datetime import datetime
from dateutil.relativedelta import relativedelta
from django.db.models import Sum
from celery import shared_task

from japb_api.celery import app
from japb_api.products.models import ProductList, ProductListItem
from japb_api.users.models import User
from japb_api.transactions.models import Transaction, TransactionItem

@app.task
# when a product list period ends, we need to renew it
# duplicate the product list and create a new one with the next period
def renew_product_lists():
    product_lists = ProductList.objects.filter(
        period_end__lte=datetime.now(), period_type="MONTHLY"
    )
    for product_list in product_lists:
        # Calculate the next period end date by adding 1 month
        # This will properly handle month boundaries (31 days, February 28/29 days)
        next_period_start = product_list.period_end
        next_period_end = next_period_start + relativedelta(months=1)

        # Create a duplicate product list with new period
        new_product_list = ProductList.objects.create(
            user=product_list.user,
            name=product_list.name,
            description=product_list.description,
            period_type=product_list.period_type,
            period_start=next_period_start,
            period_end=next_period_end,
        )

        # Copy all items from the original product list to the new one
        original_items = ProductListItem.objects.filter(product_list=product_list)
        for item in original_items:
            ProductListItem.objects.create(
                user=item.user,
                product=item.product,
                product_list=new_product_list,
                quantity=item.quantity,
                quantity_purchased=0,  # Reset purchased quantity for the new period
            )

@shared_task
def update_user_product_list_items(user_pk):
    user = User.objects.get(pk=user_pk)
    # get active product lists
    # active product lists are those that have a period_start less than or equal to the current date
    # and a period_end greater than the current date
    product_lists = ProductList.objects.filter(
        user=user,
        period_start__lte=datetime.now(),
        period_end__gt=datetime.now()
    )

    for product_list in product_lists:
        # get user transaction and then the transaction items
        transactions = Transaction.objects.filter(
            user=user,
            date__range=(product_list.period_start, product_list.period_end)
        )

        product_list_items = ProductListItem.objects.filter(product_list=product_list)

        for product_list_item in product_list_items:
            transaction_items_for_product = TransactionItem.objects.filter(
                transaction__in=transactions,
                product=product_list_item.product
            )
            product_list_item.quantity_purchased = (
                transaction_items_for_product.aggregate(Sum("quantity"))["quantity__sum"] or 0
            )
            product_list_item.save()
