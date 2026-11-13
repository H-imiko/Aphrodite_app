import os
from datetime import date, datetime, time as heure, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Sum
from django.http import FileResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.economy.models import Transaction
from apps.economy.services import ErreurEconomie
from apps.shop.models import Item
from apps.social.models import Like
from . import services
from .forms import CandidatureForm
from .models import Candidature, ExempleCandidature, PrimeCreateur

User = get_user_model()


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


def _bornes(date_reference):
    debut = date_reference.replace(day=1)
    if debut.month == 12:
        fin = debut.replace(year=debut.year + 1, month=1)
    else:
        fin = debut.replace(month=debut.month + 1)
    return debut, fin


def createurs_du_mois(request):
    """Podium public des createurs, calcule sur les ventes du mois.

    Page de reconnaissance : elle montre ce que la communaute a achete et
    aime, pas le nombre d'articles publies. Les primes ne sont annoncees
    qu'une fois versees (commande primes_createurs).
    """
    aujourd_hui = timezone.localdate()
    debut, fin = _bornes(aujourd_hui)
    # Les champs compares sont des DateTimeField : on filtre avec des bornes
    # conscientes du fuseau, sinon la comparaison part d'un minuit naif.
    debut_dt = timezone.make_aware(datetime.combine(debut, heure.min))
    fin_dt = timezone.make_aware(datetime.combine(fin, heure.min))
    mois_precedent = debut - timedelta(days=1)
    debut_precedent, _ = _bornes(mois_precedent)

    lignes = []
    createurs = (User.objects.filter(createur_valide=True, is_active=True,
                                     est_divinite=False, est_suspendu=False)
                 .order_by("pseudo_whatsapp"))
    for createur in createurs:
        nb_articles = Item.objects.filter(
            createur=createur, est_actif=True,
            date_creation__gte=debut_dt, date_creation__lt=fin_dt).count()
        ventes = Transaction.objects.filter(
            destinataire=createur, type=Transaction.Type.ACHAT,
            date__gte=debut_dt, date__lt=fin_dt)
        cubis = ventes.aggregate(t=Sum("montant"))["t"] or 0
        likes = Like.objects.filter(
                            item__createur=createur,
                date__gte=debut_dt, date__lt=fin_dt).count()
        if not nb_articles and not cubis and not likes:
            continue
        lignes.append({"user": createur, "articles": nb_articles,
                       "cubis": cubis, "likes": likes})

    lignes.sort(key=lambda l: (l["cubis"], l["likes"], l["articles"]),
                reverse=True)
    podium = lignes[:3]
    prime_precedente = (PrimeCreateur.objects
                        .filter(mois=debut_precedent.strftime("%Y-%m"))
                        .select_related("user")
                        .order_by("rang"))
    vedettes = []
    if podium:
        vedettes = list(Item.objects.filter(
            createur=podium[0]["user"], est_actif=True,
            masque_moderation=False
        ).select_related("createur").order_by("-date_creation")[:3])

    return render(request, "creators/du_mois.html", {
        "debut": debut,
        "podium": podium,
        "classement": lignes,
        "vedettes": vedettes,
        "primes": list(getattr(settings, "PRIMES_CREATEURS",
                                (5000, 2000, 1000))),
        "prime_precedente": prime_precedente,
        "mois_precedent": debut_precedent,
        "possedes": set(),
        "aimes": set(),
    })


@login_required
def exemple_image(request, pk):
    ex = get_object_or_404(
        ExempleCandidature.objects.select_related("candidature"), pk=pk)
    if not (request.user.est_divinite
            or ex.candidature.user_id == request.user.pk):
        raise PermissionDenied
    fichier = ex.image.storage.open(ex.image.name, "rb")
    return FileResponse(fichier, filename=os.path.basename(ex.image.name))