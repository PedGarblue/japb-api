from django.db import models

class Currency(models.Model):
    # some currencies are global and some are user specific
    user = models.ForeignKey('users.User', null = True, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=5, null=True)

    def __str__(self):
        return self.name