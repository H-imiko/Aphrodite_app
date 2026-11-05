from django.conf import settings
from django.db import models


class Order(models.Model):
    class Statut(models.TextChoices):
        DEMANDE = "demande", "En attente du Créateur"
        EN_COURS = "en_cours", "En cours"
        LIVREE = "livree", "Livrée"
        TERMINEE = "terminee", "Terminée"
        LITIGE = "litige", "Litige"
        REFUSEE = "refusee", "Refusée"
        ANNULEE = "annulee", "Annulée"
        REMBOURSEE = "remboursee", "Remboursée"
        EXPIREE = "expiree", "Expirée"

    acheteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="commandes_passees")
    vendeur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="commandes_recues")
    titre = models.CharField(max_length=100)
    description = models.TextField()
    prix_cubis = models.PositiveIntegerField()
    statut = models.CharField(max_length=12, choices=Statut.choices,
                              default=Statut.DEMANDE)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_acceptation = models.DateTimeField(null=True, blank=True)
    date_livraison = models.DateTimeField(null=True, blank=True)
    date_auto_confirmation = models.DateTimeField(null=True, blank=True)
    date_fin = models.DateTimeField(null=True, blank=True)
    raison_litige = models.CharField(max_length=500, blank=True)
    litige_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="litiges_ouverts")
    tranche_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="litiges_tranches")
    decision = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ["-date_creation"]

    def __str__(self):
        return f"Commande #{self.pk} : {self.titre}"


class OrderMessage(models.Model):
    commande = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="messages")
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="messages_commandes")
    texte = models.CharField(max_length=1000)
    systeme = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "id"]

    def __str__(self):
        return f"Message #{self.pk} (commande {self.commande_id})"
