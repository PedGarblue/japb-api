from datetime import date, datetime, timezone
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from japb_api.accounts.models import Account
from japb_api.currencies.models import Currency
from japb_api.expense_shares.models import (
    ExpenseShareCategoryExclude,
    ExpenseShareCategoryInclude,
    ExpenseSharePartner,
    ExpenseSharePeriod,
)
from japb_api.expense_shares.utils import (
    aggregate_partner_expenses,
    finalize_period,
    resolve_category_ids,
)
from japb_api.receivables.models import Contact, Receivable
from japb_api.receivables.utils import compute_receivable_totals
from japb_api.transactions.models import Category, Transaction
from japb_api.users.factories import UserFactory


class TestResolveCategoryIds(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.contact = Contact.objects.create(user=self.user, name="Partner")
        self.partner = ExpenseSharePartner.objects.create(
            user=self.user, contact=self.contact
        )
        self.parent = Category.objects.create(
            user=self.user,
            name="Home",
            color="#000",
            description="Home",
            type="expense",
        )
        self.child_rent = Category.objects.create(
            user=self.user,
            name="Rent",
            color="#111",
            description="Rent",
            type="expense",
            parent_category=self.parent,
        )
        self.child_utilities = Category.objects.create(
            user=self.user,
            name="Utilities",
            color="#222",
            description="Utilities",
            type="expense",
            parent_category=self.parent,
        )
        self.grandchild = Category.objects.create(
            user=self.user,
            name="Electric",
            color="#333",
            description="Electric",
            type="expense",
            parent_category=self.child_utilities,
        )
        self.other = Category.objects.create(
            user=self.user,
            name="Food",
            color="#444",
            description="Food",
            type="expense",
        )

    def test_parent_include_expands_descendants(self):
        ExpenseShareCategoryInclude.objects.create(
            partner=self.partner, category=self.parent
        )
        resolved = resolve_category_ids(self.partner)
        self.assertEqual(
            resolved,
            {
                self.parent.id,
                self.child_rent.id,
                self.child_utilities.id,
                self.grandchild.id,
            },
        )

    def test_exclude_child_and_its_descendants(self):
        ExpenseShareCategoryInclude.objects.create(
            partner=self.partner, category=self.parent
        )
        ExpenseShareCategoryExclude.objects.create(
            partner=self.partner, category=self.child_utilities
        )
        resolved = resolve_category_ids(self.partner)
        self.assertEqual(resolved, {self.parent.id, self.child_rent.id})
        self.assertNotIn(self.child_utilities.id, resolved)
        self.assertNotIn(self.grandchild.id, resolved)


class ExpenseShareAPITestCase(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.other_user = UserFactory()
        self.token = RefreshToken.for_user(self.user)
        self.usd = Currency.objects.create(name="USD", default_conversion_source=None)
        self.account = Account.objects.create(
            name="USD Account", user=self.user, currency=self.usd, decimal_places=2
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token.access_token}")

        self.parent = Category.objects.create(
            user=self.user,
            name="Home",
            color="#000",
            description="Home",
            type="expense",
        )
        self.child_rent = Category.objects.create(
            user=self.user,
            name="Rent",
            color="#111",
            description="Rent",
            type="expense",
            parent_category=self.parent,
        )
        self.child_utilities = Category.objects.create(
            user=self.user,
            name="Utilities",
            color="#222",
            description="Utilities",
            type="expense",
            parent_category=self.parent,
        )
        self.food = Category.objects.create(
            user=self.user,
            name="Food",
            color="#333",
            description="Food",
            type="expense",
        )

    def _create_partner(self, includes=None, excludes=None, percent="50.00"):
        payload = {
            "contact": "Alice",
            "default_partner_percent": percent,
            "includes": includes if includes is not None else [self.parent.id],
            "excludes": excludes if excludes is not None else [],
        }
        response = self.client.post(
            reverse("expense-share-partners-list"), payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.json()

    def _create_expense(self, category, amount_minor, day=10, description="Expense"):
        return Transaction.objects.create(
            user=self.user,
            account=self.account,
            category=category,
            amount=amount_minor,
            description=description,
            date=datetime(2022, 3, day, 12, 0, 0, tzinfo=timezone.utc),
        )


class TestExpenseSharePartnerViews(ExpenseShareAPITestCase):
    def test_create_partner_with_includes_and_excludes(self):
        body = self._create_partner(
            includes=[self.parent.id],
            excludes=[self.child_utilities.id],
        )
        self.assertEqual(body["contact_name"], "Alice")
        self.assertEqual(set(body["include_ids"]), {self.parent.id})
        self.assertEqual(set(body["exclude_ids"]), {self.child_utilities.id})
        self.assertTrue(Contact.objects.filter(user=self.user, name="Alice").exists())

    def test_other_user_cannot_see_partner(self):
        body = self._create_partner()
        other_token = RefreshToken.for_user(self.other_user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {other_token.access_token}"
        )
        response = self.client.get(
            reverse("expense-share-partners-detail", kwargs={"pk": body["id"]}),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TestExpenseSharePreviewFinalize(ExpenseShareAPITestCase):
    def setUp(self):
        super().setUp()
        self.partner_body = self._create_partner(
            includes=[self.parent.id],
            excludes=[self.child_utilities.id],
        )
        self.partner_id = self.partner_body["id"]
        # Rent: $100, Utilities: $40 (excluded), Food: $25 (not included)
        self._create_expense(self.child_rent, -10000, day=5, description="Rent")
        self._create_expense(
            self.child_utilities, -4000, day=6, description="Utilities"
        )
        self._create_expense(self.food, -2500, day=7, description="Food")

    def test_preview_totals_respect_include_exclude(self):
        response = self.client.get(
            reverse("expense-share-periods-preview"),
            {
                "partner": self.partner_id,
                "year": 2022,
                "month": 3,
                "partner_percent": "40.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(Decimal(body["total_expenses_usd"]), Decimal("100.00"))
        self.assertEqual(Decimal(body["partner_share_usd"]), Decimal("40.00"))
        self.assertEqual(Decimal(body["my_share_usd"]), Decimal("60.00"))
        self.assertEqual(len(body["lines"]), 1)
        self.assertEqual(body["lines"][0]["category_id"], self.child_rent.id)
        self.assertEqual(body["lines"][0]["transaction_count"], 1)

    def test_finalize_creates_receivable_without_linking_expense_txs(self):
        response = self.client.post(
            reverse("expense-share-periods-finalize"),
            {
                "partner": self.partner_id,
                "year": 2022,
                "month": 3,
                "partner_percent": "40.00",
                "notes": "March split",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body["status"], "finalized")
        self.assertEqual(Decimal(body["partner_share_usd"]), Decimal("40.00"))
        self.assertIsNotNone(body["receivable_id"])
        self.assertEqual(len(body["lines"]), 1)

        rec = Receivable.objects.get(pk=body["receivable_id"])
        self.assertEqual(rec.explicit_principal_usd, Decimal("40.00"))
        self.assertEqual(rec.description, "Shared expenses 2022-03")
        self.assertEqual(rec.due_date, date(2022, 4, 30))
        self.assertEqual(rec.transactions.count(), 0)

        expense_ids = set(
            Transaction.objects.filter(amount__lt=0).values_list("id", flat=True)
        )
        linked = set(rec.transactions.values_list("id", flat=True))
        self.assertTrue(expense_ids.isdisjoint(linked))

    def test_collection_reduces_outstanding(self):
        finalize = self.client.post(
            reverse("expense-share-periods-finalize"),
            {
                "partner": self.partner_id,
                "year": 2022,
                "month": 3,
                "partner_percent": "50.00",
            },
            format="json",
        )
        rec_id = finalize.json()["receivable_id"]
        payload = {
            "amount": 20.0,
            "description": "Partial share payment",
            "account": self.account.id,
            "date": datetime(2022, 4, 1, 12, 0, 0, tzinfo=timezone.utc),
            "receivable": rec_id,
        }
        response = self.client.post(reverse("transactions-list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        rec = Receivable.objects.get(pk=rec_id)
        totals = compute_receivable_totals(rec)
        self.assertEqual(totals["principal_usd"], 50.0)
        self.assertEqual(totals["paid_usd"], 20.0)
        self.assertEqual(totals["outstanding_usd"], 30.0)
        self.assertEqual(totals["status"], "UNPAID")

    def test_re_finalize_updates_same_receivable(self):
        first = self.client.post(
            reverse("expense-share-periods-finalize"),
            {
                "partner": self.partner_id,
                "year": 2022,
                "month": 3,
                "partner_percent": "50.00",
            },
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        receivable_id = first.json()["receivable_id"]
        period_id = first.json()["id"]

        # Add another rent expense and re-finalize at 40%
        self._create_expense(self.child_rent, -5000, day=20, description="Extra rent")

        second = self.client.post(
            reverse("expense-share-periods-finalize"),
            {
                "partner": self.partner_id,
                "year": 2022,
                "month": 3,
                "partner_percent": "40.00",
            },
            format="json",
        )
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        body = second.json()
        self.assertEqual(body["id"], period_id)
        self.assertEqual(body["receivable_id"], receivable_id)
        self.assertEqual(Decimal(body["total_expenses_usd"]), Decimal("150.00"))
        self.assertEqual(Decimal(body["partner_share_usd"]), Decimal("60.00"))

        rec = Receivable.objects.get(pk=receivable_id)
        self.assertEqual(rec.explicit_principal_usd, Decimal("60.00"))
        self.assertEqual(Receivable.objects.count(), 1)
        self.assertEqual(ExpenseSharePeriod.objects.count(), 1)

    def test_other_user_partner_returns_404_on_finalize(self):
        other_token = RefreshToken.for_user(self.other_user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {other_token.access_token}"
        )
        response = self.client.post(
            reverse("expense-share-periods-finalize"),
            {
                "partner": self.partner_id,
                "year": 2022,
                "month": 3,
                "partner_percent": "50.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_periods_filters_by_month(self):
        self.client.post(
            reverse("expense-share-periods-finalize"),
            {
                "partner": self.partner_id,
                "year": 2022,
                "month": 3,
                "partner_percent": "50.00",
            },
            format="json",
        )
        response = self.client.get(
            reverse("expense-share-periods-list"),
            {"year": 2022, "month": 3},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["month"], 3)


class TestFinalizeHelper(ExpenseShareAPITestCase):
    def test_aggregate_and_finalize_helper(self):
        contact = Contact.objects.create(user=self.user, name="Bob")
        partner = ExpenseSharePartner.objects.create(user=self.user, contact=contact)
        ExpenseShareCategoryInclude.objects.create(
            partner=partner, category=self.food
        )
        self._create_expense(self.food, -2000, day=1)

        aggregation = aggregate_partner_expenses(
            self.user, partner, 2022, 3, partner_percent=Decimal("50")
        )
        self.assertEqual(aggregation["total_expenses_usd"], Decimal("20.00"))
        self.assertEqual(aggregation["partner_share_usd"], Decimal("10.00"))

        period, _ = finalize_period(
            self.user, partner, 2022, 3, partner_percent=Decimal("50")
        )
        self.assertEqual(period.status, ExpenseSharePeriod.STATUS_FINALIZED)
        self.assertEqual(period.receivable.explicit_principal_usd, Decimal("10.00"))
