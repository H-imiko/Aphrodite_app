from django.conf import settings
from django.db import models


class InventoryItem(models.Model):
    proprietaire = models.ForeignKey(settings.AUTH_USER_MODEL,
                                     on_delete=models.CASCADE,
                                     related_name="inventaire")
    item = models.ForeignKey("shop.Item", on_delete=models.CASCADE,
                             related_name="possessions")
    quantite = models.PositiveIntegerField(default=1)
    date_obtention = models.DateTimeField(auto_now_add=True)
    est_relique = models.BooleanField(default=False)

    class Meta:
        unique_together = ("proprietaire", "item")
        ordering = ["-date_obtention"]

    def __str__(self):
        return f"{self.proprietaire} : {self.item}"