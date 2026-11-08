import os
from io import BytesIO

from django import forms
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from PIL import Image

from apps.shop.forms import _vraie_transparence
from .models import Offrande

MO = 1024 * 1024


class OffrandeForm(forms.ModelForm):
    class Meta:
        model = Offrande
        fields = ("nom", "prix_cubis", "image", "ordre", "est_actif")
        labels = {
            "nom": "Nom de l'offrande",
            "prix_cubis": "Prix (en Cubis)",
            "image": "Image (PNG ou WebP transparent)",
            "ordre": "Ordre d'affichage (le plus petit en premier)",
            "est_actif": "Disponible dans le catalogue",
        }
        widgets = {"image": forms.FileInput(
            attrs={"accept": "image/png,image/webp"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["image"].required = False
            self.fields["image"].label = (
                "Nouvelle image (laisse vide pour garder l'actuelle)")

    def clean_prix_cubis(self):
        prix = self.cleaned_data["prix_cubis"]
        if not 1 <= prix <= 100000:
            raise forms.ValidationError("Le prix doit être entre 1 et "
                                        "100000 Cubis.")
        return prix

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if not isinstance(image, UploadedFile):
            return image
        if os.path.splitext(image.name)[1].lower() not in (".png", ".webp"):
            raise forms.ValidationError("L'image doit être un PNG ou un WebP.")
        if image.size > 2 * MO:
            raise forms.ValidationError("Image trop lourde (2 Mo maximum).")
        if not _vraie_transparence(image):
            raise forms.ValidationError(
                "Cette image n'est pas vraiment transparente : si tu vois un "
                "damier gris et blanc, il fait partie de l'image.")
        img = Image.open(image).convert("RGBA")
        img.thumbnail((256, 256))
        tampon = BytesIO()
        img.save(tampon, "PNG", optimize=True)
        nom = os.path.splitext(os.path.basename(image.name))[0][:40] or "offrande"
        return ContentFile(tampon.getvalue(), name=f"{nom}.png")
