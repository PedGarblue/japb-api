from django.db import models


class Receivable(models.Model):
    user = models.ForeignKey("users.User", null=True, on_delete=models.CASCADE)
    description = models.CharField(max_length=500)
    contact = models.CharField(max_length=500)
    due_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.contact} - {self.description}"
