from django.contrib import messages
from django.db.models import Count
from django.contrib.auth import (login, logout, get_user_model,
                                 update_session_auth_hash)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import render, redirect, get_object_or_404

from apps.creators.models import Candidature
from apps.inventory.models import Equipement
from apps.offrandes.models import Offrande, OffrandeEnvoyee
from apps.shop.models import Item
from apps.social.models import Abonnement
from .forms import InscriptionForm, ProfilForm, SuppressionCompteForm
from .services import (SuppressionRefusee, commandes_bloquantes,
                       fermer_compte)

User = get_user_model()


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


def inscription(request):
    if request.user.is_authenticated:
        return redirect("boutique")
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


@login_required
def parametres(request):
    return render(request, "accounts/parametres.html")


@login_required
def changer_mot_de_passe(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        # Sans ca, changer le mot de passe deconnecte le membre.
        update_session_auth_hash(request, form.user)
        messages.success(request, "Mot de passe changé.")
        return redirect("parametres")
    return render(request, "accounts/mot_de_passe.html", {"form": form})


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
