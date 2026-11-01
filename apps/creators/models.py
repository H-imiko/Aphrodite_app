from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models


def stockage_prive():
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)


class Candidature(models.Model):
    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        VALIDEE = "validee", "Validée"
        REFUSEE = "refusee", "Refusée"

    class TypeCreation(models.TextChoices):
        STICKERS = "stickers", "Stickers"
        AUDIO = "audio", "Audio (Suno)"
        PHOTO = "photo", "Édition photo"
        VIDEO = "video", "Édition vidéo"

    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name="candidatures")
    types_creation = models.JSONField(default=list)
    message = models.TextField(blank=True)
    statut = models.CharField(max_length=15, choices=Statut.choices,
                              default=Statut.EN_ATTENTE)
    motif_refus = models.CharField(max_length=300, blank=True)
    traitee_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                    blank=True, on_delete=models.SET_NULL,
                                    related_name="candidatures_traitees")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_traitement = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date_creation"]

    def __str__(self):
        return f"Candidature de {self.user} ({self.get_statut_display()})"

    @property
    def types_affiches(self):
        noms = dict(self.TypeCreation.choices)
        return ", ".join(noms.get(t, t) for t in self.types_creation)


class ExempleCandidature(models.Model):
    candidature = models.ForeignKey(Candidature, on_delete=models.CASCADE,
                                    related_name="exemples")
    image = models.ImageField(upload_to="candidatures/",
                              storage=stockage_prive)