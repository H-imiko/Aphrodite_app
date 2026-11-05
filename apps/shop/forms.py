from django import forms
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

from .models import Item

NOMS_COURTS = {
    "stickers": "Stickers",
    "fonds": "Fonds d'écran",
    "image_rp": "Images RP",
    "autre": "Autres",
}
PRIX_MAX = 1_000_000


class ArticleForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ("titre", "description", "prix_cubis", "categorie", "image")
        widgets = {"image": forms.FileInput(attrs={"accept": "image/*"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        conseils = [
            f"{NOMS_COURTS.get(cat, cat)} {mini}–{maxi}"
            for cat, (mini, maxi) in settings.PRIX_CONSEILLES.items()
        ]
        self.fields["prix_cubis"].help_text = (
            "Prix conseillés (en Cubis) : " + " · ".join(conseils))
        if self.instance and self.instance.pk:
            self.fields["image"].required = False
            self.fields["image"].label = (
                "Nouvelle image (laisse vide pour garder l'actuelle)")

    def clean_prix_cubis(self):
        prix = self.cleaned_data["prix_cubis"]
        if prix < 1:
            raise forms.ValidationError("Le prix doit être d'au moins 1 Cubis.")
        if prix > PRIX_MAX:
            raise forms.ValidationError(f"Le prix maximum est {PRIX_MAX} Cubis.")
        return prix

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if isinstance(image, UploadedFile) and image.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Image trop lourde (5 Mo maximum).")
        return image
