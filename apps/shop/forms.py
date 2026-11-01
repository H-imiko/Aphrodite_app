from django import forms
from django.conf import settings

from .models import Item

NOMS_COURTS = {
    "stickers": "Stickers",
    "fonds": "Fonds d'écran",
    "image_rp": "Images RP",
    "autre": "Autres",
}


class ArticleForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ("titre", "description", "prix_cubis", "categorie", "image")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        conseils = [
            f"{NOMS_COURTS.get(cat, cat)} {mini}–{maxi}"
            for cat, (mini, maxi) in settings.PRIX_CONSEILLES.items()
        ]
        self.fields["prix_cubis"].help_text = (
            "Prix conseillés (en Cubis) : " + " · ".join(conseils))

    def clean_prix_cubis(self):
        prix = self.cleaned_data["prix_cubis"]
        if prix < 1:
            raise forms.ValidationError("Le prix doit être d'au moins 1 Cubis.")
        return prix

    def clean_image(self):
        image = self.cleaned_data["image"]
        if image.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Image trop lourde (5 Mo maximum).")
        return image