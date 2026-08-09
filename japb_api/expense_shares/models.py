from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class ExpenseSharePartner(models.Model):
    user = models.ForeignKey("users.User", on_delete=models.CASCADE)
    contact = models.ForeignKey(
        "receivables.Contact",
        related_name="expense_share_partners",
        on_delete=models.PROTECT,
    )
    is_active = models.BooleanField(default=True)
    default_partner_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "contact"],
                name="unique_expense_share_partner_per_user_contact",
            ),
        ]

    def __str__(self):
        return f"{self.contact.name}"


class ExpenseShareCategoryInclude(models.Model):
    partner = models.ForeignKey(
        ExpenseSharePartner,
        related_name="includes",
        on_delete=models.CASCADE,
    )
    category = models.ForeignKey(
        "transactions.Category",
        related_name="expense_share_includes",
        on_delete=models.CASCADE,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["partner", "category"],
                name="unique_expense_share_include",
            ),
        ]


class ExpenseShareCategoryExclude(models.Model):
    partner = models.ForeignKey(
        ExpenseSharePartner,
        related_name="excludes",
        on_delete=models.CASCADE,
    )
    category = models.ForeignKey(
        "transactions.Category",
        related_name="expense_share_excludes",
        on_delete=models.CASCADE,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["partner", "category"],
                name="unique_expense_share_exclude",
            ),
        ]


class ExpenseSharePeriod(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_FINALIZED = "finalized"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "draft"),
        (STATUS_FINALIZED, "finalized"),
    ]

    user = models.ForeignKey("users.User", on_delete=models.CASCADE)
    partner = models.ForeignKey(
        ExpenseSharePartner,
        related_name="periods",
        on_delete=models.CASCADE,
    )
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT
    )
    partner_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    total_expenses_usd = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00")
    )
    partner_share_usd = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00")
    )
    my_share_usd = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00")
    )
    receivable = models.OneToOneField(
        "receivables.Receivable",
        related_name="expense_share_period",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    notes = models.CharField(max_length=500, blank=True, default="")
    finalized_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "partner", "year", "month"],
                name="unique_expense_share_period",
            ),
        ]

    def __str__(self):
        return f"{self.partner} {self.year}-{self.month:02d}"


class ExpenseShareLine(models.Model):
    period = models.ForeignKey(
        ExpenseSharePeriod,
        related_name="lines",
        on_delete=models.CASCADE,
    )
    category = models.ForeignKey(
        "transactions.Category",
        related_name="expense_share_lines",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    expense_total_usd = models.DecimalField(max_digits=14, decimal_places=2)
    partner_share_usd = models.DecimalField(max_digits=14, decimal_places=2)
    transaction_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        name = self.category.name if self.category_id else "Uncategorized"
        return f"{name}: {self.expense_total_usd}"
