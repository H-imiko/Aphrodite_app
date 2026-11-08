from django.conf import settings
from django.db import models


class Abonnement(models.Model):
    """Un membre suit un Créateur."""
    abonne = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="abonnements")
    createur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="abonnes")
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("abonne", "createur")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.abonne} suit {self.createur}"


class Like(models.Model):
    """Un membre aime un article."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="likes")
    item = models.ForeignKey(
        "shop.Item", on_delete=models.CASCADE, related_name="likes")
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "item")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.user} aime {self.item}"
