import os

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

from apps.commun.limites import depasse
from apps.creators.models import Candidature
from apps.inventory.models import Equipement
from apps.offrandes.models import Offrande, OffrandeEnvoyee
from apps.shop.models import Item
from apps.social.models import Abonnement
from .forms import (InscriptionForm, MotDePasseOublieForm, ProfilForm,
                    SuppressionCompteForm)
from .models import DemandeAcces
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
                "erreur_limite": (
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
            "erreur_limite": ("Trop de tentatives d'inscription depuis ce "
                              "réseau. Réessaie dans un quart d'heure."),
        }, status=429)
    form = InscriptionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        if user.type_compte == "createur":
            messages.info(
                request,
                "Dernière étape : présente tes créations pour devenir Créateur 🎨")
            return redirect("postuler")
        messages.success(
            request, "Bienvenue sur Aphrodite ✨ Personnalise ton profil !")
        return redirect("modifier_profil")
    return render(request, "accounts/inscription.html", {"form": form})


def reglement(request):
    return render(request, "reglement.html")


def mot_de_passe_oublie(request):
    """Enregistre une demande ; l'equipe la traite depuis le panel.

    Aucun email n'est envoye (le projet n'a pas de service d'email) : la
    reponse est la meme que l'adresse existe ou non, pour ne pas reveler
    qui est inscrit.
    """
    if request.method == "POST" and depasse("mot_de_passe_oublie", request):
        return render(request, "accounts/mot_de_passe_oublie.html", {
            "erreur_limite": ("Trop de demandes depuis ce réseau. "
                              "Réessaie plus tard.")}, status=429)
    form = MotDePasseOublieForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        DemandeAcces.objects.create(email=form.cleaned_data["email"])
        return render(request, "accounts/mot_de_passe_oublie.html",
                      {"envoye": True})
    return render(request, "accounts/mot_de_passe_oublie.html", {"form": form})


def photo_membre(request, pk, champ):
    """Sert une photo de profil depuis le stockage prive.

    Une photo marquee mature n'est visible que par son proprietaire et par
    les membres qui ont accepte le contenu mature. Le flou du navigateur
    n'est plus la seule protection.
    """
    if champ not in ("avatar", "banniere"):
        raise Http404
    m = get_object_or_404(User, pk=pk, is_active=True)
    fichier = getattr(m, champ)
    if not fichier:
        raise Http404
    if m.profil_mature:
        if not request.user.is_authenticated:
            raise PermissionDenied
        if m.pk != request.user.pk and not request.user.afficher_mature:
            raise PermissionDenied
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
        messages.success(request, "Mot de passe changé.")
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
        messages.success(request, "Ton compte est supprimé. Merci d'avoir joué.")
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
        messages.success(request, "Profil mis à jour ✨")
        return redirect("membre", pk=request.user.pk)
    return render(request, "accounts/modifier_profil.html", {
        "form": form, "equip": _equipement(request.user)})
