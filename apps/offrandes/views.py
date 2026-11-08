from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.economy.services import ErreurEconomie
from . import services
from .forms import OffrandeForm
from .models import Blocage, Offrande, OffrandeEnvoyee

User = get_user_model()


def _divinite(user):
    if not user.est_divinite:
        raise PermissionDenied


@login_required
def envoyer(request, pk):
    dest = get_object_or_404(User, pk=pk, is_active=True)
    if dest.pk == request.user.pk:
        messages.error(request,
                       "Tu ne peux pas t'envoyer une offrande à toi-même.")
        return redirect("membre", pk=pk)
    erreur = ""
    if request.method == "POST":
        try:
            offrande_id = int(request.POST.get("offrande", ""))
        except ValueError:
            offrande_id = None
        if offrande_id is None:
            erreur = "Choisis une offrande."
        else:
            try:
                services.envoyer(
                    request.user, dest.pk, offrande_id,
                    request.POST.get("message", ""),
                    bool(request.POST.get("anonyme")))
                messages.success(request, "Offrande envoyée 🌹")
                return redirect("membre", pk=dest.pk)
            except ErreurEconomie as e:
                erreur = str(e)
    return render(request, "offrandes/envoyer.html", {
        "dest": dest, "erreur": erreur,
        "offrandes": Offrande.objects.filter(est_actif=True),
        "choix": request.POST.get("offrande", "")})


@login_required
def recues(request, pk):
    membre = get_object_or_404(User, pk=pk, is_active=True)
    est_moi = membre.pk == request.user.pk
    dons = (OffrandeEnvoyee.objects.filter(destinataire=membre)
            .select_related("offrande", "expediteur"))
    if not est_moi:
        dons = dons.filter(masque=False)
    return render(request, "offrandes/recues.html", {
        "membre": membre, "est_moi": est_moi, "dons": dons[:80]})


@login_required
@require_POST
def masquer(request, pk):
    try:
        services.basculer_masque(request.user, pk)
    except ErreurEconomie as e:
        messages.error(request, str(e))
    return redirect("offrandes_recues", pk=request.user.pk)


@login_required
@require_POST
def bloquer(request, pk):
    try:
        services.bloquer(request.user, pk)
        messages.success(
            request, "Membre bloqué : il ne peut plus t'envoyer d'offrande, "
                     "et ses offrandes sont masquées.")
    except ErreurEconomie as e:
        messages.error(request, str(e))
    return redirect("offrandes_recues", pk=request.user.pk)


@login_required
def blocages(request):
    liste = Blocage.objects.filter(bloqueur=request.user).select_related(
        "bloque")
    return render(request, "offrandes/blocages.html", {"blocages": liste})


@login_required
@require_POST
def debloquer(request, pk):
    try:
        services.debloquer(request.user, pk)
        messages.success(request, "Membre débloqué.")
    except ErreurEconomie as e:
        messages.error(request, str(e))
    return redirect("blocages")


# ---------- Catalogue (Divinités) ----------

@login_required
def admin_catalogue(request):
    _divinite(request.user)
    form = OffrandeForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Offrande ajoutée au catalogue ✨")
        return redirect("offrandes_admin")
    return render(request, "offrandes/admin_catalogue.html", {
        "form": form, "offrandes": Offrande.objects.all()})


@login_required
def admin_modifier(request, pk):
    _divinite(request.user)
    offrande = get_object_or_404(Offrande, pk=pk)
    form = OffrandeForm(request.POST or None, request.FILES or None,
                        instance=offrande)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Offrande modifiée ✨")
        return redirect("offrandes_admin")
    return render(request, "offrandes/admin_form.html",
                  {"form": form, "offrande": offrande})


@login_required
@require_POST
def admin_basculer(request, pk):
    _divinite(request.user)
    offrande = get_object_or_404(Offrande, pk=pk)
    offrande.est_actif = not offrande.est_actif
    offrande.save(update_fields=["est_actif"])
    messages.success(request, "Offrande disponible." if offrande.est_actif
                     else "Offrande retirée du catalogue.")
    return redirect("offrandes_admin")
