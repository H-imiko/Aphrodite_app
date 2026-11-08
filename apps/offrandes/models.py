from django.conf import settings
from django.db import models


class Offrande(models.Model):
    """Un cadeau du catalogue (rose, cœur, ourson…), créé par les Divinités."""
    nom = models.CharField(max_length=60)
    prix_cubis = models.PositiveIntegerField()
    image = models.ImageField(upload_to="offrandes/")
    est_actif = models.BooleanField(default=True)
    ordre = models.PositiveIntegerField(default=0)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ordre", "prix_cubis", "id"]

    def __str__(self):
        return self.nom


class OffrandeEnvoyee(models.Model):
    expediteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="offrandes_envoyees")
    destinataire = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="offrandes_recues")
    offrande = models.ForeignKey(
        Offrande, on_delete=models.PROTECT, related_name="dons")
    message = models.CharField(max_length=150, blank=True)
    anonyme = models.BooleanField(default=False)
    prix_paye = models.PositiveIntegerField(default=0)
    masque = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.offrande} : {self.expediteur} → {self.destinataire}"


class Blocage(models.Model):
    """Un membre ne veut plus recevoir d'offrandes d'un autre membre."""
    bloqueur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="blocages_faits")
    bloque = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="blocages_subis")
    via_anonyme = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("bloqueur", "bloque")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.bloqueur} bloque {self.bloque}"
