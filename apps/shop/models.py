from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.db import models
from PIL import Image, ImageFilter


def stockage_prive():
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)


class Item(models.Model):
    class Categorie(models.TextChoices):
        STICKERS = "stickers", "Stickers"
        FONDS = "fonds", "Fonds d'écran / Photos de profil"
        IMAGE_RP = "image_rp", "Images RP (armes, sortilèges, auras…)"
        AUTRE = "autre", "Autres créations visuelles"

    titre = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    prix_cubis = models.PositiveIntegerField()
    categorie = models.CharField(max_length=20, choices=Categorie.choices,
                                 default=Categorie.AUTRE)
    # Original : stocké dans un dossier privé
    image = models.ImageField(upload_to="items/", storage=stockage_prive)
    # Version floutée publique, créée automatiquement
    apercu = models.ImageField(upload_to="apercus/", blank=True, editable=False)
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
        img = img.convert("RGB")
        img.thumbnail((500, 500))
        img = img.filter(ImageFilter.GaussianBlur(radius=14))
        tampon = BytesIO()
        img.save(tampon, "JPEG", quality=70)
        self.apercu.save(f"apercu_{self.pk}.jpg",
                         ContentFile(tampon.getvalue()), save=False)
        Item.objects.filter(pk=self.pk).update(apercu=self.apercu.name)
