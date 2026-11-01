from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()


class MembreChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.pseudo_whatsapp} ({obj.get_espece_display()})"


class CubisForm(forms.Form):
    destinataire = MembreChoice(queryset=User.objects.none())
    montant = forms.IntegerField(min_value=1)
    message = forms.CharField(required=False, max_length=200)

    def __init__(self, *args, qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        if qs is not None:
            self.fields["destinataire"].queryset = qs