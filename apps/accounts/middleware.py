from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import translation

# Pages accessibles meme quand un mot de passe provisoire doit etre change.
CHEMINS_LIBRES = ("/static/", "/media/", "/private_media/")


class LangueUtilisateurMiddleware:
    """Affiche le site dans la langue choisie dans les parametres.

    LocaleMiddleware a deja lu la session, le cookie et l'en-tete du
    navigateur ; la langue du profil est plus explicite, elle gagne.
    """

    CODES = {code for code, _ in settings.LANGUAGES}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        code = getattr(user, "langue", "") if user and user.is_authenticated else ""
        if code in self.CODES:
            translation.activate(code)
            request.LANGUAGE_CODE = code
        return self.get_response(request)


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
