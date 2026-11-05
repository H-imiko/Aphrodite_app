from django.conf import settings
from django.db import models


class Transaction(models.Model):
    class Type(models.TextChoices):
        CONNEXION = "connexion_quotidienne", "Connexion quotidienne"
        ENVOI_DIVINITE = "envoi_divinite", "Envoi des Divinités"
        TRANSFERT = "transfert_membre", "Transfert entre membres"
        ACHAT = "achat", "Achat"
        VENTE = "vente", "Vente"
        BONUS_CREATEUR = "bonus_createur", "Bonus Créateur"
        REMBOURSEMENT = "remboursement", "Remboursement"
        DESTRUCTION = "destruction", "Cubis détruits (achat officiel)"
        SANCTION = "sanction", "Réduction de Cubis (sanction)"
        SEQUESTRE = "sequestre", "Cubis bloqués (commande)"
        LIBERATION = "liberation", "Paiement d'une commande"

    # expediteur vide = Trésor (système)
    expediteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="transactions_envoyees")
    # destinataire vide = Cubis détruits ou bloqués
    destinataire = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.CASCADE, related_name="transactions_recues")
    # Divinité qui a déclenché un envoi du Trésor
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="transactions_distribuees")
    montant = models.PositiveIntegerField()
    type = models.CharField(max_length=30, choices=Type.choices)
    description = models.CharField(max_length=200, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.get_type_display()} : {self.montant} Cubis"
