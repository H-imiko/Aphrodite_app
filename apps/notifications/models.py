from django.conf import settings
from django.db import models


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="notifications")
    titre = models.CharField(max_length=120)
    message = models.CharField(max_length=300, blank=True)
    lien = models.CharField(max_length=200, blank=True)
    type = models.CharField(max_length=20, default="info")
    lu = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["user", "lu"])]

    def __str__(self):
        return f"{self.titre} → {self.user}"
