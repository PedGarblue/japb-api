from django.db import models


class Contact(models.Model):
    user = models.ForeignKey("users.User", on_delete=models.CASCADE)
    name = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"], name="unique_contact_per_user"
            ),
        ]

    def __str__(self):
        return self.name


class Receivable(models.Model):
    user = models.ForeignKey("users.User", null=True, on_delete=models.CASCADE)
    description = models.CharField(max_length=500)
    contact = models.ForeignKey(
        Contact, related_name="receivables", on_delete=models.PROTECT
    )
    due_date = models.DateField()
    # Optional principal not backed by linked transactions (e.g. expense shares).
    explicit_principal_usd = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.contact.name} - {self.description}"
