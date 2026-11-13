from django.shortcuts import redirect
from django.urls import reverse

# Pages accessibles meme quand un mot de passe provisoire doit etre change.
CHEMINS_LIBRES = ("/static/", "/media/", "/private_media/")


class MotDePasseProvisoireMiddleware:
    """Un mot de passe genere par une Divinite ne donne pas un compte.

    Tant que le membre n'a pas choisi son propre mot de passe, il ne peut
    faire qu'une chose : le changer (ou se deconnecter). Ainsi, la Divinite
    qui a transmis le mot de passe provisoire n'a plus acces au compte des
    la premiere connexion du membre.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if (user.is_authenticated
                and getattr(user, "doit_changer_mot_de_passe", False)
                and not request.path.startswith(CHEMINS_LIBRES)):
            autorises = {reverse("changer_mot_de_passe"),
                         reverse("deconnexion"),
                         reverse("admin:logout")}
            if request.path not in autorises:
                return redirect("changer_mot_de_passe")
        return self.get_response(request)
