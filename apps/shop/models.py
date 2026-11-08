from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.db import models
from PIL import Image, ImageFilter

COSMETIQUES = ("cadre", "decor")
MEDIAS = ("audio", "video")


def stockage_prive():
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)


class Item(models.Model):
    class Categorie(models.TextChoices):
        STICKERS = "stickers", "Stickers"
        FONDS = "fonds", "Fonds d'écran / Photos de profil"
        IMAGE_RP = "image_rp", "Images RP (armes, sortilèges, auras…)"
        AUDIO = "audio", "Musiques / Thèmes Suno"
        VIDEO = "video", "Vidéos"
        CADRE = "cadre", "Cadres de profil (officiel)"
        DECOR = "decor", "Décors de profil (officiel)"
        AUTRE = "autre", "Autres créations visuelles"

    titre = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    prix_cubis = models.PositiveIntegerField()
    categorie = models.CharField(max_length=20, choices=Categorie.choices,
                                 default=Categorie.AUTRE)
    # Image principale : original privé (pochette ou vignette pour audio/vidéo)
    image = models.ImageField(upload_to="items/", storage=stockage_prive)
    # Aperçu public, créé automatiquement
    apercu = models.ImageField(upload_to="apercus/", blank=True, editable=False)
    # Audio / vidéo : fichier complet (privé) et extrait gratuit
    fichier = models.FileField(upload_to="medias/", storage=stockage_prive,
                               blank=True)
    extrait = models.FileField(upload_to="extraits/", storage=stockage_prive,
                               blank=True)
    createur = models.ForeignKey(settings.AUTH_USER_MODEL,
                                 on_delete=models.CASCADE,
                                 related_name="articles")
    est_officiel = models.BooleanField(default=False)
    est_mis_en_avant = models.BooleanField(default=False)
    est_actif = models.BooleanField(default=True)
    masque_moderation = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-est_mis_en_avant", "-date_creation"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._image_initiale = self.image.name if self.image else None

    def __str__(self):
        return self.titre

    @property
    def est_media(self):
        return self.categorie in MEDIAS

    @property
    def est_cosmetique(self):
        return self.categorie in COSMETIQUES

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.image and self.image.name != self._image_initiale:
            self._generer_apercu()
            self._image_initiale = self.image.name

    def _generer_apercu(self):
        self.image.open("rb")
        img = Image.open(self.image)
        img.load()
        self.image.close()
        tampon = BytesIO()
        if self.categorie in COSMETIQUES:
            # cadres et décors : aperçu net, avec transparence
            img = img.convert("RGBA")
            img.thumbnail((400, 400))
            img.save(tampon, "PNG")
            nom = f"apercu_{self.pk}.png"
        elif self.categorie in MEDIAS:
            # pochette ou vignette : nette (le contenu payant est le fichier)
            img = img.convert("RGB")
            img.thumbnail((500, 500))
            img.save(tampon, "JPEG", quality=80)
            nom = f"apercu_{self.pk}.jpg"
        else:
            # images vendues : aperçu flouté
            img = img.convert("RGB")
            img.thumbnail((500, 500))
            img = img.filter(ImageFilter.GaussianBlur(radius=14))
            img.save(tampon, "JPEG", quality=70)
            nom = f"apercu_{self.pk}.jpg"
        self.apercu.save(nom, ContentFile(tampon.getvalue()), save=False)
        Item.objects.filter(pk=self.pk).update(apercu=self.apercu.name)
