from datetime import date, datetime, timezone

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from japb_api.accounts.models import Account
from japb_api.currencies.models import Currency, CurrencyConversionHistorial
from japb_api.receivables.models import Contact, Receivable
from japb_api.transactions.models import Transaction
from japb_api.users.factories import UserFactory


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
        self.assertEqual(Contact.objects.count(), 1)
        rec = Receivable.objects.get()
        self.assertEqual(rec.contact.name, "Alice")
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

    def test_collection_by_contact_without_receivable_id(self):
        self.test_loan_transaction_creates_receivable_with_explicit_due_date()
        payload = {
            "amount": 100.50,
            "description": "Repayment by contact",
            "account": self.account.id,
            "date": datetime(2022, 3, 1, 12, 0, 0, tzinfo=timezone.utc),
            "contact": "Alice",
        }
        response = self.client.post(reverse("transactions-list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.json()), 1)
        coll = Transaction.objects.filter(amount__gt=0).get()
        self.assertEqual(coll.receivable_id, Receivable.objects.get().id)

    def test_collection_by_contact_splits_across_two_receivables(self):
        contact = Contact.objects.create(user=self.user, name="Alice")
        rec1 = Receivable.objects.create(
            user=self.user,
            contact=contact,
            description="Loan 1",
            due_date=date(2022, 1, 1),
        )
        rec2 = Receivable.objects.create(
            user=self.user,
            contact=contact,
            description="Loan 2",
            due_date=date(2022, 2, 1),
        )
        Transaction.objects.create(
            user=self.user,
            account=self.account,
            receivable=rec1,
            amount=-10000,
            description="Loan 1",
            date=datetime(2022, 1, 1, tzinfo=timezone.utc),
        )
        Transaction.objects.create(
            user=self.user,
            account=self.account,
            receivable=rec2,
            amount=-5000,
            description="Loan 2",
            date=datetime(2022, 1, 2, tzinfo=timezone.utc),
        )
        payload = {
            "amount": 120.0,
            "description": "Bulk repayment",
            "account": self.account.id,
            "date": datetime(2022, 3, 1, 12, 0, 0, tzinfo=timezone.utc),
            "contact": "Alice",
        }
        response = self.client.post(reverse("transactions-list"), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.json()), 2)
        collections = {
            t.receivable_id: t
            for t in Transaction.objects.filter(amount__gt=0)
        }
        self.assertEqual(collections[rec1.id].amount, 10000)
        self.assertEqual(collections[rec2.id].amount, 2000)

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
        self.assertEqual(body["contact_name"], "Alice")
        self.assertEqual(len(body["transactions"]), 2)

    def test_list_contacts_with_totals(self):
        self.test_collection_by_contact_without_receivable_id()
        response = self.client.get(reverse("contacts-list"), format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Alice")
        self.assertEqual(results[0]["total_principal_usd"], 100.50)
        self.assertEqual(results[0]["total_paid_usd"], 100.50)
        self.assertEqual(results[0]["total_outstanding_usd"], 0.0)
        self.assertEqual(results[0]["receivable_count"], 1)

    def test_list_receivables_grouped_by_contact(self):
        self.test_collection_by_contact_splits_across_two_receivables()
        response = self.client.get(
            reverse("receivables-list"), {"group_by": "contact"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        groups = response.json()
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["contact"], "Alice")
        self.assertEqual(groups[0]["total_principal_usd"], 150.0)
        self.assertEqual(groups[0]["total_paid_usd"], 120.0)
        self.assertEqual(groups[0]["total_outstanding_usd"], 30.0)
        self.assertEqual(len(groups[0]["receivables"]), 2)

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
        other_contact = Contact.objects.create(user=self.other_user, name="Other")
        rec = Receivable.objects.create(
            user=self.other_user,
            contact=other_contact,
            description="Other",
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

    def test_collection_unknown_contact_returns_400(self):
        payload = {
            "amount": 10.0,
            "description": "Unknown",
            "account": self.account.id,
            "date": datetime(2022, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            "contact": "Nobody",
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
        self.assertEqual(detail.json()["principal_usd"], 100.0)

    def test_can_update_receivable_metadata(self):
        contact = Contact.objects.create(user=self.user, name="Old contact")
        Receivable.objects.create(
            user=self.user,
            contact=contact,
            description="Old",
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
        self.assertEqual(rec.contact.name, "New contact")

    def test_can_delete_receivable(self):
        contact = Contact.objects.create(user=self.user, name="C")
        Receivable.objects.create(
            user=self.user,
            contact=contact,
            description="Del",
            due_date=date(2022, 1, 1),
        )
        rec = Receivable.objects.get()
        response = self.client.delete(
            reverse("receivables-detail", kwargs={"pk": rec.id}), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Receivable.objects.count(), 0)

    def test_explicit_principal_usd_without_transactions(self):
        contact = Contact.objects.create(user=self.user, name="Partner")
        rec = Receivable.objects.create(
            user=self.user,
            contact=contact,
            description="Shared expenses 2022-01",
            due_date=date(2022, 2, 28),
            explicit_principal_usd="75.50",
        )
        response = self.client.get(
            reverse("receivables-detail", kwargs={"pk": rec.id}), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body["explicit_principal_usd"], "75.50")
        self.assertEqual(body["principal_usd"], 75.50)
        self.assertEqual(body["paid_usd"], 0.0)
        self.assertEqual(body["outstanding_usd"], 75.50)
        self.assertEqual(body["status"], "UNPAID")
        self.assertEqual(body["transactions"], [])

    def test_explicit_principal_plus_collection_and_loan_tx(self):
        contact = Contact.objects.create(user=self.user, name="Partner")
        rec = Receivable.objects.create(
            user=self.user,
            contact=contact,
            description="Mixed principal",
            due_date=date(2022, 2, 28),
            explicit_principal_usd="50.00",
        )
        Transaction.objects.create(
            user=self.user,
            account=self.account,
            receivable=rec,
            amount=-2500,
            description="Extra principal tx",
            date=datetime(2022, 1, 10, tzinfo=timezone.utc),
        )
        Transaction.objects.create(
            user=self.user,
            account=self.account,
            receivable=rec,
            amount=4000,
            description="Partial repay",
            date=datetime(2022, 2, 1, tzinfo=timezone.utc),
        )
        response = self.client.get(
            reverse("receivables-detail", kwargs={"pk": rec.id}), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body["principal_usd"], 75.0)
        self.assertEqual(body["paid_usd"], 40.0)
        self.assertEqual(body["outstanding_usd"], 35.0)
        self.assertEqual(body["status"], "UNPAID")

    def test_explicit_principal_usd_is_read_only_on_api(self):
        contact = Contact.objects.create(user=self.user, name="Partner")
        rec = Receivable.objects.create(
            user=self.user,
            contact=contact,
            description="Shared",
            due_date=date(2022, 2, 28),
            explicit_principal_usd="10.00",
        )
        response = self.client.patch(
            reverse("receivables-detail", kwargs={"pk": rec.id}),
            {"explicit_principal_usd": "99.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rec.refresh_from_db()
        self.assertEqual(str(rec.explicit_principal_usd), "10.00")
