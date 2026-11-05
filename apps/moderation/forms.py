from django import forms

from .models import Report


class SignalementForm(forms.Form):
    motif = forms.ChoiceField(choices=Report.Motif.choices, label="Motif")
    details = forms.CharField(
        label="Précisions (facultatif)", required=False, max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}))
