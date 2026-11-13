from datetime import date
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.files.uploadedfile import UploadedFile
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import User


class InscriptionForm(UserCreationForm):
    date_naissance = forms.DateField(
        label="Date de naissance",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    accepte_cgu = forms.BooleanField(
        label="J'ai 18 ans ou plus et j'accepte le règlement"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Le libellé de la case contient un vrai lien vers le règlement :
        # Django échappe les libellés, mark_safe n'est utilisé que pour ce
        # texte constant, avec une URL produite par reverse().
        self.fields["accepte_cgu"].label = mark_safe(
            "J'ai 18 ans ou plus et j'accepte "
            f'<a href="{reverse("reglement")}">le règlement</a>')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "pseudo_whatsapp", "espece",
                  "type_compte", "date_naissance")

    def clean_date_naissance(self):
        d = self.cleaned_data["date_naissance"]
        t = date.today()
        age = t.year - d.year - ((t.month, t.day) < (d.month, d.day))
        if age < 18:
            raise forms.ValidationError(
                "Aphrodite est réservé aux personnes de 18 ans et plus.")
        return d


class MotDePasseOublieForm(forms.Form):
    email = forms.EmailField(
        label="Ton adresse email",
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )


class SuppressionCompteForm(forms.Form):
    mot_de_passe = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    confirmer = forms.BooleanField(
        label="Je comprends que mon profil et mes données personnelles "
              "seront effacés et que je ne pourrai pas les récupérer.",
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_mot_de_passe(self):
        mot_de_passe = self.cleaned_data["mot_de_passe"]
        if not self.user or not self.user.check_password(mot_de_passe):
            raise forms.ValidationError("Mot de passe incorrect.")
        return mot_de_passe


class ProfilForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("avatar", "banniere", "pseudo_whatsapp", "titre",
                  "bio_rp", "numero_whatsapp",
                  "profil_mature", "afficher_mature")
        labels = {
            "avatar": "Photo de profil",
            "banniere": "Bannière",
            "pseudo_whatsapp": "Pseudo",
            "titre": "Bulle de pensée (court)",
            "bio_rp": "Biographie RP",
            "numero_whatsapp": "Numéro WhatsApp (jamais public, visible "
                               "seulement lors d'une commande)",
            "profil_mature": "Ma photo ou ma bannière contient du contenu "
                             "suggestif (sera floutée pour les autres)",
            "afficher_mature": "Afficher le contenu mature des autres "
                               "sans flou",
        }
        widgets = {
            "avatar": forms.FileInput(attrs={"accept": "image/*"}),
            "banniere": forms.FileInput(attrs={"accept": "image/*"}),
            "titre": forms.TextInput(attrs={
                "maxlength": 60, "placeholder": "Ex : Reine des ombres 🌙"}),
            "bio_rp": forms.Textarea(attrs={"rows": 4, "maxlength": 500}),
        }

    def _verifier_image(self, nom, limite_mo):
        image = self.cleaned_data.get(nom)
        if isinstance(image, UploadedFile) and image.size > limite_mo * 1024 * 1024:
            raise forms.ValidationError(
                f"Image trop lourde ({limite_mo} Mo maximum).")
        return image

    def clean_avatar(self):
        return self._verifier_image("avatar", 3)

    def clean_banniere(self):
        return self._verifier_image("banniere", 5)

    def clean_bio_rp(self):
        bio = self.cleaned_data.get("bio_rp", "")
        if len(bio) > 500:
            raise forms.ValidationError("500 caractères maximum.")
        return bio
