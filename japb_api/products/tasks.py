from japb_api.celery import app
from japb_api.products.models import ProductList, ProductListItem
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


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
