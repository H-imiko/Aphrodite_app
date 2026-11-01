import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from apps.economy.services import ErreurEconomie
from . import services
from .forms import CandidatureForm
from .models import Candidature, ExempleCandidature


def _divinites_seulement(user):
    if not user.est_divinite:
        raise PermissionDenied


@login_required
def postuler(request):
    if request.user.createur_valide:
        messages.info(request, "Tu es déjà Créateur validé ✨")
        return redirect("membre", pk=request.user.pk)
    derniere = request.user.candidatures.first()
    if derniere and derniere.statut == Candidature.Statut.EN_ATTENTE:
        return render(request, "creators/postuler.html",
                      {"en_attente": True, "derniere": derniere})
    form = CandidatureForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            c = Candidature.objects.create(
                user=request.user,
                types_creation=form.cleaned_data["types_creation"],
                message=form.cleaned_data["message"])
            for f in form.cleaned_data["exemples"]:
                ExempleCandidature.objects.create(candidature=c, image=f)
        messages.success(request, "Candidature envoyée ! Une Divinité va l'examiner 🎨")
        return redirect("postuler")
    return render(request, "creators/postuler.html",
                  {"form": form, "derniere": derniere, "en_attente": False})


@login_required
def candidatures(request):
    _divinites_seulement(request.user)
    en_attente = (Candidature.objects
                  .filter(statut=Candidature.Statut.EN_ATTENTE)
                  .select_related("user").order_by("date_creation"))
    traitees = (Candidature.objects
                .exclude(statut=Candidature.Statut.EN_ATTENTE)
                .select_related("user", "traitee_par")
                .order_by("-date_traitement")[:20])
    return render(request, "creators/candidatures.html",
                  {"en_attente": en_attente, "traitees": traitees})


@login_required
def candidature(request, pk):
    _divinites_seulement(request.user)
    c = get_object_or_404(
        Candidature.objects.select_related("user", "traitee_par"), pk=pk)
    return render(request, "creators/candidature.html", {"c": c})


@login_required
@require_POST
def candidature_valider(request, pk):
    _divinites_seulement(request.user)
    try:
        services.valider(pk, request.user)
        messages.success(request, "Créateur validé, +500 Cubis versés 🎉")
    except ErreurEconomie as e:
        messages.error(request, str(e))
    return redirect("candidatures")


@login_required
@require_POST
def candidature_refuser(request, pk):
    _divinites_seulement(request.user)
    motif = request.POST.get("motif", "").strip()[:300]
    try:
        services.refuser(pk, request.user, motif)
        messages.success(request, "Candidature refusée.")
    except ErreurEconomie as e:
        messages.error(request, str(e))
    return redirect("candidatures")


@login_required
def exemple_image(request, pk):
    ex = get_object_or_404(
        ExempleCandidature.objects.select_related("candidature"), pk=pk)
    if not (request.user.est_divinite
            or ex.candidature.user_id == request.user.pk):
        raise PermissionDenied
    fichier = ex.image.storage.open(ex.image.name, "rb")
    return FileResponse(fichier, filename=os.path.basename(ex.image.name))