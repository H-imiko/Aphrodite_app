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


class Equipement(models.Model):
    """Ce qu'un membre affiche sur son profil."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL,
                                on_delete=models.CASCADE,
                                related_name="equipement")
    cadre = models.ForeignKey("shop.Item", null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="+")
    decor = models.ForeignKey("shop.Item", null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="+")
    musique = models.ForeignKey("shop.Item", null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="+")

    def __str__(self):
        return f"Équipement de {self.user}"


class ObjectTransfer(models.Model):
    """Cadeau d'un objet de l'inventaire à un autre membre."""

    class Statut(models.TextChoices):
        ENVOYE = "envoye", "En attente"
        ACCEPTE = "accepte", "Accepté"
        REFUSE = "refuse", "Refusé"
        ANNULE = "annule", "Annulé"
        EXPIRE = "expire", "Expiré"

    expediteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="cadeaux_envoyes")
    destinataire = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="cadeaux_recus")
    item = models.ForeignKey("shop.Item", on_delete=models.CASCADE,
                             related_name="cadeaux")
    message = models.CharField(max_length=200, blank=True)
    statut = models.CharField(max_length=10, choices=Statut.choices,
                              default=Statut.ENVOYE)
    date = models.DateTimeField(auto_now_add=True)
    date_reponse = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Cadeau « {self.item} » : {self.expediteur} → {self.destinataire}"
