from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    class Action(models.TextChoices):
        ENVOI_CUBIS = "envoi_cubis", "Envoi de Cubis (Trésor)"
        CANDIDATURE_VALIDEE = "candidature_validee", "Créateur validé"
        CANDIDATURE_REFUSEE = "candidature_refusee", "Candidature refusée"
        ARTICLE_MASQUE = "article_masque", "Article masqué"
        ARTICLE_AFFICHE = "article_affiche", "Article réaffiché"
        AVERTISSEMENT = "avertissement", "Avertissement"
        SUSPENSION = "suspension", "Suspension"
        FIN_SUSPENSION = "fin_suspension", "Suspension levée"
        RETRAIT_CREATEUR = "retrait_createur", "Statut Créateur retiré"
        REDUCTION_CUBIS = "reduction_cubis", "Réduction de Cubis"
        SIGNALEMENT_CLASSE = "signalement_classe", "Signalement classé"
        LITIGE_RESOLU = "litige_resolu", "Litige de commande tranché"

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


class Report(models.Model):
    class Motif(models.TextChoices):
        MINEUR = "mineur", "Personnage ou personne mineure"
        ILLEGAL = "illegal", "Contenu illégal"
        PHOTO_REELLE = "photo_reelle", "Photo d'une vraie personne"
        HARDCORE = "hardcore", "Contenu explicite interdit dans l'application"
        HARCELEMENT = "harcelement", "Harcèlement ou menaces"
        ARNAQUE = "arnaque", "Arnaque ou non-livraison"
        COPIE = "copie", "Création copiée ou volée"
        AUTRE = "autre", "Autre"

    class Statut(models.TextChoices):
        OUVERT = "ouvert", "Ouvert"
        TRAITE = "traite", "Traité"
        CLASSE = "classe", "Classé sans suite"

    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="signalements_faits")
    article = models.ForeignKey(
        "shop.Item", null=True, blank=True, on_delete=models.CASCADE,
        related_name="signalements")
    membre = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.CASCADE, related_name="signalements_recus")
    motif = models.CharField(max_length=20, choices=Motif.choices)
    details = models.CharField(max_length=500, blank=True)
    statut = models.CharField(max_length=10, choices=Statut.choices,
                              default=Statut.OUVERT)
    traite_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="signalements_traites")
    date = models.DateTimeField(auto_now_add=True)
    date_traitement = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Signalement #{self.pk} ({self.get_motif_display()})"


class Sanction(models.Model):
    class Type(models.TextChoices):
        AVERTISSEMENT = "avertissement", "Avertissement"
        SUSPENSION = "suspension", "Suspension"
        RETRAIT_CREATEUR = "retrait_createur", "Retrait du statut Créateur"
        REDUCTION_CUBIS = "reduction_cubis", "Réduction de Cubis"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="sanctions")
    type = models.CharField(max_length=20, choices=Type.choices)
    raison = models.CharField(max_length=300)
    duree_jours = models.PositiveIntegerField(null=True, blank=True)
    montant = models.PositiveIntegerField(null=True, blank=True)
    par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="sanctions_donnees")
    signalement = models.ForeignKey(
        Report, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="sanctions")
    vu = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.get_type_display()} → {self.user}"
