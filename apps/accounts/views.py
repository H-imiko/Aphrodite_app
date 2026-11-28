import os

from django.conf import settings
from django.contrib import messages
from django.db.models import Count
from django.contrib.auth import (login, logout, get_user_model,
                                 update_session_auth_hash)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import views as auth_views
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils import translation
from django.utils.translation import gettext as _

from apps.commun.limites import depasse
from apps.creators.models import Candidature
from apps.inventory.models import Equipement
from apps.offrandes.models import Offrande, OffrandeEnvoyee
from apps.shop.models import Item
from apps.social.models import Abonnement
from .forms import (InscriptionForm, MotDePasseOublieForm, ProfilForm,
                    ReinitialisationMotDePasseForm, SuppressionCompteForm)
from .models import DemandeAcces, LANGUES
from .services import (SuppressionRefusee, commandes_bloquantes,
                       fermer_compte)

User = get_user_model()
TYPES_PHOTO = {".png": "image/png", ".jpg": "image/jpeg",
               ".jpeg": "image/jpeg", ".webp": "image/webp",
               ".gif": "image/gif"}


def _equipement(membre):
    """Cadre, décor et musique affichés sur le profil (None si absents)."""
    equip = (Equipement.objects.filter(user=membre)
             .select_related("cadre", "decor", "musique").first())
    if equip is None:
        return None
    if equip.musique and not equip.musique.est_actif:
        equip.musique = None
    return equip


def accueil(request):
    if request.user.is_authenticated:
        return redirect("boutique")
    en_vente = Item.objects.filter(est_actif=True, masque_moderation=False)
    return render(request, "accueil.html", {
        "articles": en_vente.select_related("createur")
                            .order_by("-est_mis_en_avant", "-date_creation")[:4],
        "nb_membres": User.objects.filter(is_active=True).count(),
        "nb_articles": en_vente.count(),
        "possedes": set(),
        "aimes": set(),
    })


class ConnexionVue(auth_views.LoginView):
    """Connexion limitee en debit, pour rendre le brute-force inutile."""

    template_name = "accounts/connexion.html"
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        email = (request.POST.get("username") or "").strip().lower()
        # Deux compteurs : par compte vise, et par adresse tous comptes
        # confondus (un attaquant qui change d'email a chaque essai reste
        # bloque par le second).
        if depasse("connexion", request, email) or depasse("connexion_ip",
                                                           request):
            return render(request, self.template_name, {
                "form": self.get_form(),
                "erreur_limite": _(
                    "Trop de tentatives de connexion. Patiente quelques "
                    "minutes avant de réessayer."),
            }, status=429)
        return super().post(request, *args, **kwargs)


def inscription(request):
    if request.user.is_authenticated:
        return redirect("boutique")
    if request.method == "POST" and depasse("inscription", request):
        return render(request, "accounts/inscription.html", {
            "form": InscriptionForm(request.POST),
            "erreur_limite": _("Trop de tentatives d'inscription depuis ce "
                              "réseau. Réessaie dans un quart d'heure."),
        }, status=429)
    form = InscriptionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        if user.type_compte == "createur":
            messages.info(
                request,
                _("Dernière étape : présente tes créations pour devenir "
                  "Créateur 🎨"))
            return redirect("postuler")
        messages.success(
            request, _("Bienvenue sur Aphrodite ✨ Personnalise ton profil !"))
        return redirect("modifier_profil")
    return render(request, "accounts/inscription.html", {"form": form})


def reglement(request):
    return render(request, "reglement.html")


def confidentialite(request):
    return render(request, "confidentialite.html")


class MotDePasseOublieVue(auth_views.PasswordResetView):
    """Envoie par email un lien pour choisir un nouveau mot de passe.

    La confirmation est la meme que l'adresse existe ou non : la page ne
    revele pas qui est inscrit.
    """

    template_name = "accounts/mot_de_passe_oublie.html"
    email_template_name = "accounts/emails/reinitialisation.txt"
    subject_template_name = "accounts/emails/reinitialisation_sujet.txt"
    form_class = ReinitialisationMotDePasseForm
    success_url = reverse_lazy("mot_de_passe_envoye")

    def post(self, request, *args, **kwargs):
        if depasse("mot_de_passe_oublie", request):
            return render(request, self.template_name, {
                "form": self.get_form(),
                "erreur_limite": _("Trop de demandes depuis ce réseau. "
                                   "Réessaie plus tard.")}, status=429)
        return super().post(request, *args, **kwargs)


class ReinitialiserMotDePasseVue(auth_views.PasswordResetConfirmView):
    """Le lien reçu par email permet de choisir un nouveau mot de passe."""

    template_name = "accounts/reinitialiser_mot_de_passe.html"
    success_url = reverse_lazy("connexion")

    def form_valid(self, form):
        reponse = super().form_valid(form)
        # Le mot de passe choisi par le membre n'est plus provisoire.
        User.objects.filter(pk=form.user.pk).update(
            doit_changer_mot_de_passe=False)
        messages.success(self.request,
                         _("Mot de passe changé. Tu peux te connecter."))
        return reponse


def demande_acces(request):
    """Demande manuelle, pour un membre qui n'a plus acces a son email.

    L'equipe verifie l'identite sur WhatsApp depuis le panel, puis genere
    un mot de passe provisoire. La reponse est la meme que l'adresse existe
    ou non, pour ne pas reveler qui est inscrit.
    """
    if request.method == "POST" and depasse("mot_de_passe_oublie", request):
        return render(request, "accounts/mot_de_passe_demande.html", {
            "erreur_limite": _("Trop de demandes depuis ce réseau. "
                               "Réessaie plus tard.")}, status=429)
    form = MotDePasseOublieForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        DemandeAcces.objects.create(email=form.cleaned_data["email"])
        return render(request, "accounts/mot_de_passe_demande.html",
                      {"envoye": True})
    return render(request, "accounts/mot_de_passe_demande.html",
                  {"form": form})


def photo_membre(request, pk, champ):
    """Sert une photo de profil depuis le stockage prive.

    Le fichier n'est jamais expose en direct : cette vue verifie que la
    photo existe et pose les en-tetes de cache et de non-indexation.
    """
    if champ not in ("avatar", "banniere"):
        raise Http404
    m = get_object_or_404(User, pk=pk, is_active=True)
    fichier = getattr(m, champ)
    if not fichier:
        raise Http404
    extension = os.path.splitext(fichier.name)[1].lower()
    reponse = FileResponse(
        fichier.storage.open(fichier.name, "rb"),
        content_type=TYPES_PHOTO.get(extension, "application/octet-stream"))
    reponse["X-Content-Type-Options"] = "nosniff"
    reponse["X-Robots-Tag"] = "noindex"
    reponse["Cache-Control"] = "private, max-age=3600"
    return reponse


@login_required
def parametres(request):
    return render(request, "accounts/parametres.html")


@login_required
def changer_langue(request):
    """Enregistre la langue de l'interface (profil et cookie).

    Le profil garde le choix d'un appareil a l'autre ; le cookie est celui
    que LocaleMiddleware lit, il couvre l'avant-connexion (pages publiques).
    """
    if request.method != "POST":
        return redirect("parametres")
    code = (request.POST.get("langue") or "").strip()
    noms = dict(LANGUES)
    if code not in noms:
        messages.error(request, _("Langue inconnue."))
        return redirect("parametres")
    translation.activate(code)
    User.objects.filter(pk=request.user.pk).update(langue=code)
    request.user.langue = code
    messages.success(request, _("Langue enregistrée."))
    reponse = redirect("parametres")
    reponse.set_cookie(settings.LANGUAGE_COOKIE_NAME, code,
                       max_age=365 * 24 * 3600, samesite="Lax")
    return reponse


@login_required
def changer_mot_de_passe(request):
    provisoire = request.user.doit_changer_mot_de_passe
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        # Sans ca, changer le mot de passe deconnecte le membre.
        update_session_auth_hash(request, form.user)
        if provisoire:
            User.objects.filter(pk=request.user.pk).update(
                doit_changer_mot_de_passe=False)
        messages.success(request, _("Mot de passe changé."))
        return redirect("parametres")
    return render(request, "accounts/mot_de_passe.html",
                  {"form": form, "provisoire": provisoire})


@login_required
def supprimer_compte(request):
    commandes = list(commandes_bloquantes(request.user))
    if commandes:
        # Refus explicite : on montre les commandes à régler, pas de formulaire.
        return render(request, "accounts/supprimer_compte.html",
                      {"commandes": commandes})
    form = SuppressionCompteForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            fermer_compte(request.user)
        except SuppressionRefusee as refus:
            messages.error(request, str(refus))
            return redirect("supprimer_compte")
        logout(request)
        messages.success(request,
                         _("Ton compte est supprimé. Merci d'avoir joué."))
        return redirect("accueil")
    return render(request, "accounts/supprimer_compte.html", {"form": form})


@login_required
def profil(request):
    return redirect("membre", pk=request.user.pk)


@login_required
def membre(request, pk):
    m = get_object_or_404(User, pk=pk, is_active=True)
    articles = []
    if m.peut_publier:
        articles = Item.objects.filter(createur=m, est_actif=True)
    est_moi = m.pk == request.user.pk
    candidature_en_cours = est_moi and Candidature.objects.filter(
        user=m, statut=Candidature.Statut.EN_ATTENTE).exists()
    return render(request, "accounts/membre.html", {
        "membre": m, "articles": articles, "est_moi": est_moi,
        "equip": _equipement(m),
        "offrandes": list(Offrande.objects.filter(
            dons__destinataire=m, dons__masque=False
        ).annotate(n=Count("dons")).order_by("-n")[:12]),
        "nb_offrandes": OffrandeEnvoyee.objects.filter(
            destinataire=m, masque=False).count(),
        "nb_abonnes": m.abonnes.count(),
        "nb_abonnements": m.abonnements.count(),
        "suis": (not est_moi and Abonnement.objects.filter(
            abonne=request.user, createur=m).exists()),
        "candidature_en_cours": candidature_en_cours})


@login_required
def modifier_profil(request):
    form = ProfilForm(request.POST or None, request.FILES or None,
                      instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Profil mis à jour ✨"))
        return redirect("membre", pk=request.user.pk)
    return render(request, "accounts/modifier_profil.html", {
        "form": form, "equip": _equipement(request.user)})
