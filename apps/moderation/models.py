from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    class Action(models.TextChoices):
        ENVOI_CUBIS = "envoi_cubis", "Envoi de Cubis (Trésor)"
        CANDIDATURE_VALIDEE = "candidature_validee", "Créateur validé"
        CANDIDATURE_REFUSEE = "candidature_refusee", "Candidature refusée"
        ARTICLE_MASQUE = "article_masque", "Article masqué"
        ARTICLE_AFFICHE = "article_affiche", "Article réaffiché"

    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="actions_divinite")
    action = models.CharField(max_length=40, choices=Action.choices)
    cible = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="actions_subies")
    details = models.CharField(max_length=300, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.get_action_display()} ({self.date:%d/%m/%Y})"