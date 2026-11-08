import os

from django import forms
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from PIL import Image

from .models import COSMETIQUES, MEDIAS, Item

NOMS_COURTS = {
    "stickers": "Stickers",
    "fonds": "Fonds d'écran",
    "image_rp": "Images RP",
    "audio": "Audio",
    "video": "Vidéo",
    "autre": "Autres",
}
PRIX_MAX = 1_000_000
MO = 1024 * 1024
# extensions autorisées et poids maximum, par catégorie
REGLES = {
    "audio": {"fichier": ((".mp3", ".m4a", ".ogg", ".wav"), 25),
              "extrait": ((".mp3", ".m4a", ".ogg"), 3)},
    "video": {"fichier": ((".mp4", ".webm"), 100),
              "extrait": ((".mp4", ".webm"), 10)},
}


def _vraie_transparence(fichier):
    """Vrai si l'image a un canal de transparence réellement utilisé.
    Un PNG enregistré depuis un site avec un damier gris et blanc n'a pas de
    transparence : le damier fait partie de l'image."""
    try:
        fichier.seek(0)
        img = Image.open(fichier)
        a_alpha = img.mode in ("RGBA", "LA") or (
            img.mode == "P" and "transparency" in img.info)
        if not a_alpha:
            return False
        histogramme = img.convert("RGBA").getchannel("A").histogram()
        total = sum(histogramme)
        return total > 0 and sum(histogramme[:10]) / total >= 0.05
    except Exception:
        return False
    finally:
        try:
            fichier.seek(0)
        except Exception:
            pass


class ArticleForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ("titre", "description", "prix_cubis", "categorie",
                  "image", "fichier", "extrait")
        labels = {
            "image": "Image (pochette ou vignette pour l'audio et la vidéo ; "
                     "PNG transparent pour un cadre ou un décor)",
            "fichier": "Fichier complet (audio ou vidéo) : privé, accessible "
                       "après l'achat",
            "extrait": "Extrait public (audio : environ 30 secondes ; "
                       "vidéo : un court extrait)",
        }
        widgets = {
            "image": forms.FileInput(attrs={"accept": "image/*"}),
            "fichier": forms.FileInput(attrs={"accept": "audio/*,video/*"}),
            "extrait": forms.FileInput(attrs={"accept": "audio/*,video/*"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        conseils = [
            f"{NOMS_COURTS.get(cat, cat)} {mini}–{maxi}"
            for cat, (mini, maxi) in settings.PRIX_CONSEILLES.items()
        ]
        self.fields["prix_cubis"].help_text = (
            "Prix conseillés (en Cubis) : " + " · ".join(conseils))
        for nom in ("fichier", "extrait"):
            self.fields[nom].required = False
        if not (user and user.est_divinite):
            self.fields["categorie"].choices = [
                (v, n) for v, n in Item.Categorie.choices
                if v not in COSMETIQUES]
        if self.instance and self.instance.pk:
            self.fields["image"].required = False
            self.fields["image"].label = (
                "Nouvelle image (laisse vide pour garder l'actuelle)")
            self.fields["categorie"].disabled = True

    def clean_prix_cubis(self):
        prix = self.cleaned_data["prix_cubis"]
        if prix < 1:
            raise forms.ValidationError("Le prix doit être d'au moins 1 Cubis.")
        if prix > PRIX_MAX:
            raise forms.ValidationError(f"Le prix maximum est {PRIX_MAX} Cubis.")
        return prix

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if isinstance(image, UploadedFile) and image.size > 5 * MO:
            raise forms.ValidationError("Image trop lourde (5 Mo maximum).")
        return image

    def _verifier_fichier(self, champ, cat, valeur):
        extensions, max_mo = REGLES[cat][champ]
        if isinstance(valeur, UploadedFile):
            ext = os.path.splitext(valeur.name)[1].lower()
            if ext not in extensions:
                self.add_error(champ, "Format accepté : "
                               + ", ".join(extensions) + ".")
            elif valeur.size > max_mo * MO:
                self.add_error(champ, f"Fichier trop lourd ({max_mo} Mo "
                                      "maximum).")

    def clean(self):
        data = super().clean()
        cat = data.get("categorie")
        image = data.get("image")
        if cat in COSMETIQUES and isinstance(image, UploadedFile):
            if os.path.splitext(image.name)[1].lower() not in (".png", ".webp"):
                self.add_error("image", "Un cadre ou un décor doit être un "
                                        "PNG ou WebP transparent.")
            elif not _vraie_transparence(image):
                self.add_error(
                    "image",
                    "Cette image n'est pas vraiment transparente : si tu vois "
                    "un damier gris et blanc, il fait partie de l'image. "
                    "Utilise un PNG avec un vrai fond transparent.")
        if cat in MEDIAS:
            fichier = data.get("fichier") or self.instance.fichier
            extrait = data.get("extrait") or self.instance.extrait
            if not fichier:
                self.add_error("fichier", "Le fichier complet est obligatoire.")
            if not extrait:
                self.add_error("extrait", "L'extrait public est obligatoire.")
            self._verifier_fichier("fichier", cat, data.get("fichier"))
            self._verifier_fichier("extrait", cat, data.get("extrait"))
        else:
            data["fichier"] = None
            data["extrait"] = None
        return data
