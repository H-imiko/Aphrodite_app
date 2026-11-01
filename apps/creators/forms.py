from django import forms

from .models import Candidature


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"accept": "image/*"}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        nettoyer = super().clean
        if isinstance(data, (list, tuple)):
            return [nettoyer(d, initial) for d in data]
        return [nettoyer(data, initial)]


class CandidatureForm(forms.Form):
    types_creation = forms.MultipleChoiceField(
        label="Que crées-tu ?",
        choices=Candidature.TypeCreation.choices,
        widget=forms.CheckboxSelectMultiple)
    message = forms.CharField(
        label="Présente-toi (facultatif)", required=False, max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}))
    exemples = MultipleFileField(
        label="1 à 3 captures d'exemples de tes créations", required=False)

    def clean_exemples(self):
        fichiers = self.cleaned_data.get("exemples") or []
        if not 1 <= len(fichiers) <= 3:
            raise forms.ValidationError(
                "Envoie entre 1 et 3 captures d'écran.")
        champ_image = forms.ImageField()
        propres = []
        for f in fichiers:
            if f.size > 5 * 1024 * 1024:
                raise forms.ValidationError(
                    "Une image est trop lourde (5 Mo maximum).")
            propres.append(champ_image.clean(f))
        return propres