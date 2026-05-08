from datetime import date, datetime, timezone

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from japb_api.accounts.models import Account
from japb_api.currencies.models import Currency, CurrencyConversionHistorial
from japb_api.transactions.models import Transaction
from japb_api.users.factories import UserFactory

from ..models import Receivable


class TestReceivableViews(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.other_user = UserFactory()
        self.token = RefreshToken.for_user(self.user)
        self.usd = Currency.objects.create(name="USD", default_conversion_source=None)
        self.account = Account.objects.create(
            name="USD Account", user=self.user, currency=self.usd, decimal_places=2
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token.access_token}")

    def test_loan_transaction_creates_receivable_with_explicit_due_date(self):
        payload = {
            "amount": -100.50,
            "description": "Loan to Alice",
            "account": self.account.id,
            "date": datetime(2022, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            "is_loan": True,
            "contact": "Alice",
            "loan_due_date": "2022-06-01",
        }
        response = self.client.post(reverse("transactions-list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Receivable.objects.count(), 1)
        rec = Receivable.objects.get()
        self.assertEqual(rec.contact, "Alice")
        self.assertEqual(rec.description, "Loan to Alice")
        self.assertEqual(rec.due_date, date(2022, 6, 1))
        self.assertEqual(str(rec.user_id), str(self.user.id))
        tx = Transaction.objects.get()
        self.assertEqual(tx.receivable_id, rec.id)
        self.assertEqual(tx.amount, -10050)

    def test_loan_transaction_default_due_date_one_month_after_transaction_date(self):
        payload = {
            "amount": -10.0,
            "description": "Loan default due",
            "account": self.account.id,
            "date": datetime(2022, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            "is_loan": True,
            "contact": "Bob",
        }
        response = self.client.post(reverse("transactions-list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        rec = Receivable.objects.get()
        self.assertEqual(rec.due_date, date(2022, 2, 15))

    def test_collection_positive_transaction_links_receivable(self):
        self.test_loan_transaction_creates_receivable_with_explicit_due_date()
        rec = Receivable.objects.get()
        payload = {
            "amount": 100.50,
            "description": "Repayment",
            "account": self.account.id,
            "date": datetime(2022, 3, 1, 12, 0, 0, tzinfo=timezone.utc),
            "receivable": rec.id,
        }
        response = self.client.post(reverse("transactions-list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        coll = Transaction.objects.filter(amount__gt=0).get()
        self.assertEqual(coll.receivable_id, rec.id)

    def test_get_receivable_detail_returns_transactions_and_usd_totals(self):
        self.test_collection_positive_transaction_links_receivable()
        rec = Receivable.objects.get()
        url = reverse("receivables-detail", kwargs={"pk": rec.id})
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body["principal_usd"], 100.50)
        self.assertEqual(body["paid_usd"], 100.50)
        self.assertEqual(body["outstanding_usd"], 0.0)
        self.assertEqual(body["status"], "PAID")
        self.assertEqual(len(body["transactions"]), 2)
        descriptions = {t["description"] for t in body["transactions"]}
        self.assertEqual(descriptions, {"Loan to Alice", "Repayment"})

    def test_is_loan_with_positive_amount_returns_400(self):
        payload = {
            "amount": 50.0,
            "description": "Invalid loan",
            "account": self.account.id,
            "date": datetime(2022, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            "is_loan": True,
            "contact": "X",
        }
        response = self.client.post(reverse("transactions-list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Receivable.objects.count(), 0)

    def test_receivable_belonging_to_other_user_returns_400(self):
        Account.objects.create(
            name="Other USD", user=self.other_user, currency=self.usd, decimal_places=2
        )
        rec = Receivable.objects.create(
            user=self.other_user,
            description="Other",
            contact="C",
            due_date=date(2022, 1, 1),
        )
        payload = {
            "amount": 10.0,
            "description": "Bad link",
            "account": self.account.id,
            "date": datetime(2022, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            "receivable": rec.id,
        }
        response = self.client.post(reverse("transactions-list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_principal_usd_uses_conversion_for_non_usd_account(self):
        ves = Currency.objects.create(
            name="VES", default_conversion_source="paralelo"
        )
        ves_account = Account.objects.create(
            name="VES", user=self.user, currency=ves, decimal_places=2
        )
        historial = CurrencyConversionHistorial.objects.create(
            currency_from=ves,
            currency_to=self.usd,
            rate=60.0,
            source="paralelo",
        )
        # auto_now_add ignores date= on create; back-date for transaction lookup
        CurrencyConversionHistorial.objects.filter(pk=historial.pk).update(
            date=datetime(2022, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
        )
        payload = {
            "amount": -6000.0,
            "description": "Loan VES",
            "account": ves_account.id,
            "date": datetime(2022, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            "is_loan": True,
            "contact": "Maria",
        }
        response = self.client.post(reverse("transactions-list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        rec = Receivable.objects.get()
        detail = self.client.get(
            reverse("receivables-detail", kwargs={"pk": rec.id}), format="json"
        )
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        # -6000 VES / 60 = 100 USD principal
        self.assertEqual(detail.json()["principal_usd"], 100.0)

    def test_can_update_receivable_metadata(self):
        Receivable.objects.create(
            user=self.user,
            description="Old",
            contact="Old contact",
            due_date=date(2022, 1, 1),
        )
        rec = Receivable.objects.get()
        response = self.client.patch(
            reverse("receivables-detail", kwargs={"pk": rec.id}),
            {"description": "New desc", "contact": "New contact"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rec.refresh_from_db()
        self.assertEqual(rec.description, "New desc")
        self.assertEqual(rec.contact, "New contact")

    def test_can_delete_receivable(self):
        Receivable.objects.create(
            user=self.user,
            description="Del",
            contact="C",
            due_date=date(2022, 1, 1),
        )
        rec = Receivable.objects.get()
        response = self.client.delete(
            reverse("receivables-detail", kwargs={"pk": rec.id}), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Receivable.objects.count(), 0)
