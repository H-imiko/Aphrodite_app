from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Sum
from django.shortcuts import render, redirect

from .forms import CubisForm
from .models import Transaction
from .services import ErreurEconomie, transferer, envoyer_par_divinite

User = get_user_model()


@login_required
def portefeuille(request):
    membres = (User.objects.filter(is_active=True)
               .exclude(pk=request.user.pk).order_by("pseudo_whatsapp"))
    form = CubisForm(request.POST or None, qs=membres)
    if request.method == "POST" and form.is_valid():
        try:
            transferer(request.user, form.cleaned_data["destinataire"],
                       form.cleaned_data["montant"],
                       form.cleaned_data["message"])
            messages.success(request, "Cubis envoyés ✨")
            return redirect("portefeuille")
        except ErreurEconomie as e:
            form.add_error(None, str(e))
    return render(request, "economy/portefeuille.html", {"form": form})


@login_required
def transactions(request):
    historique = (Transaction.objects
                  .filter(Q(expediteur=request.user)
                          | Q(destinataire=request.user)
                          | Q(auteur=request.user))
                  .select_related("expediteur", "destinataire", "auteur")
                  .distinct()[:100])
    return render(request, "economy/transactions.html",
                  {"historique": historique})


@login_required
def tresor(request):
    if not request.user.est_divinite:
        raise PermissionDenied
    membres = User.objects.filter(is_active=True).order_by("pseudo_whatsapp")
    form = CubisForm(request.POST or None, qs=membres)
    if request.method == "POST" and form.is_valid():
        try:
            envoyer_par_divinite(request.user, form.cleaned_data["destinataire"],
                                 form.cleaned_data["montant"],
                                 form.cleaned_data["message"])
            messages.success(request, "Récompense envoyée depuis le Trésor ✨")
            return redirect("tresor")
        except ErreurEconomie as e:
            form.add_error(None, str(e))
    recents = (Transaction.objects
               .filter(type=Transaction.Type.ENVOI_DIVINITE)
               .select_related("destinataire", "auteur")[:30])
    total = User.objects.aggregate(t=Sum("solde_cubis"))["t"] or 0
    return render(request, "economy/tresor.html",
                  {"form": form, "recents": recents, "total": total})