from django.contrib import messages
from django.contrib.auth import login, get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from apps.creators.models import Candidature
from apps.shop.models import Item
from .forms import InscriptionForm, ProfilForm

User = get_user_model()


def accueil(request):
    if request.user.is_authenticated:
        return redirect("boutique")
    return render(request, "accueil.html")


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


@login_required
def profil(request):
    return redirect("membre", pk=request.user.pk)


@login_required
def membre(request, pk):
    m = get_object_or_404(User, pk=pk, is_active=True)
    articles = []
    if m:
        articles = Item.objects.filter(createur=m, est_actif=True)
    est_moi = m.pk == request.user.pk
    candidature_en_cours = est_moi and Candidature.objects.filter(
        user=m, statut=Candidature.Statut.EN_ATTENTE).exists()
    return render(request, "accounts/membre.html", {
        "membre": m, "articles": articles, "est_moi": est_moi,
        "candidature_en_cours": candidature_en_cours})


@login_required
def modifier_profil(request):
    form = ProfilForm(request.POST or None, request.FILES or None,
                      instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profil mis à jour ✨")
        return redirect("membre", pk=request.user.pk)
    return render(request, "accounts/modifier_profil.html", {"form": form})