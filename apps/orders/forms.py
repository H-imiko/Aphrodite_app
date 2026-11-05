from django import forms


class CommandeForm(forms.Form):
    titre = forms.CharField(
        label="Titre de la commande", max_length=100,
        widget=forms.TextInput(attrs={"maxlength": 100}))
    description = forms.CharField(
        label="Décris précisément ce que tu veux", max_length=2000,
        widget=forms.Textarea(attrs={"rows": 6, "maxlength": 2000}))
    prix = forms.IntegerField(
        label="Ton prix (en Cubis)", min_value=1, max_value=1_000_000)
