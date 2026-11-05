from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.economy.services import ErreurEconomie
from . import services
from .forms import CommandeForm
from .models import Order

User = get_user_model()
S = Order.Statut
ACTIVES = (S.DEMANDE, S.EN_COURS, S.LIVREE, S.LITIGE)


def _commande(request, pk):
    c = get_object_or_404(
        Order.objects.select_related(
            "acheteur", "vendeur", "tranche_par", "litige_par"), pk=pk)
    u = request.user
    est_partie = u.pk in (c.acheteur_id, c.vendeur_id)
    arbitre = u.est_divinite and (c.statut == S.LITIGE
                                  or c.tranche_par_id == u.pk)
    if not (est_partie or arbitre):
        raise PermissionDenied
    return c, est_partie


@login_required
def liste(request):
    services.traiter_echeances()
    passees = (Order.objects.filter(acheteur=request.user)
               .select_related("vendeur"))
    recues = (Order.objects.filter(vendeur=request.user)
              .select_related("acheteur"))
    return render(request, "orders/liste.html",
                  {"passees": passees, "recues": recues})


@login_required
def nouvelle(request, vendeur_id):
    vendeur = get_object_or_404(User, pk=vendeur_id, is_active=True)
    form = CommandeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            c = services.creer_demande(
                request.user, vendeur, form.cleaned_data["titre"],
                form.cleaned_data["description"], form.cleaned_data["prix"])
            messages.success(
                request, "Demande envoyée ! Tes Cubis ne sont bloqués que "
                         "si le Créateur accepte.")
            return redirect("commande", pk=c.pk)
        except ErreurEconomie as e:
            form.add_error(None, str(e))
    return render(request, "orders/nouvelle.html",
                  {"form": form, "vendeur": vendeur})


@login_required
def detail(request, pk):
    services.traiter_echeances()
    c, est_partie = _commande(request, pk)
    u = request.user
    est_acheteur = u.pk == c.acheteur_id
    est_vendeur = u.pk == c.vendeur_id
    peut_trancher = (u.est_divinite and not est_partie
                     and c.statut == S.LITIGE)
    numero = ""
    if est_vendeur and c.statut in (S.EN_COURS, S.LIVREE, S.LITIGE):
        numero = c.acheteur.numero_whatsapp
    return render(request, "orders/detail.html", {
        "c": c,
        "fil": c.messages.select_related("auteur"),
        "est_acheteur": est_acheteur,
        "est_vendeur": est_vendeur,
        "numero": numero,
        "fonds_bloques": c.statut in (S.EN_COURS, S.LIVREE, S.LITIGE),
        "peut_accepter": est_vendeur and c.statut == S.DEMANDE,
        "peut_annuler_demande": est_acheteur and c.statut == S.DEMANDE,
        "peut_livrer": est_vendeur and c.statut == S.EN_COURS,
        "peut_confirmer": est_acheteur and c.statut in (S.EN_COURS, S.LIVREE),
        "peut_annuler_vendeur": est_vendeur and c.statut == S.EN_COURS,
        "peut_litige": est_partie and c.statut in (S.EN_COURS, S.LIVREE),
        "peut_trancher": peut_trancher,
        "peut_ecrire": (est_partie and c.statut in ACTIVES) or peut_trancher,
    })


@login_required
@require_POST
def action(request, pk):
    a = request.POST.get("action")
    u = request.user
    try:
        if a == "accepter":
            services.accepter(u, pk)
            messages.success(request, "Commande acceptée : les Cubis sont "
                                      "bloqués. Tu peux commencer !")
        elif a == "refuser":
            services.refuser(u, pk)
            messages.success(request, "Demande refusée.")
        elif a == "annuler_demande":
            services.annuler_demande(u, pk)
            messages.success(request, "Demande annulée.")
        elif a == "livrer":
            services.livrer(u, pk, request.POST.get("message", ""))
            messages.success(request, "Commande marquée comme livrée.")
        elif a == "confirmer":
            services.confirmer(u, pk)
            messages.success(request, "Merci ! Le Créateur a été payé.")
        elif a == "annuler_vendeur":
            services.annuler_par_vendeur(u, pk)
            messages.success(request, "Commande annulée, l'acheteur est "
                                      "remboursé.")
        elif a == "litige":
            services.ouvrir_litige(u, pk, request.POST.get("raison", ""))
            messages.success(request, "Litige ouvert : une Divinité va "
                                      "examiner la commande.")
        else:
            raise ErreurEconomie("Action inconnue.")
    except ErreurEconomie as e:
        messages.error(request, str(e))
    return redirect("commande", pk=pk)


@login_required
@require_POST
def message(request, pk):
    try:
        services.poster_message(request.user, pk, request.POST.get("texte", ""))
    except ErreurEconomie as e:
        messages.error(request, str(e))
    return redirect("commande", pk=pk)


@login_required
@require_POST
def trancher(request, pk):
    try:
        services.trancher(request.user, pk, request.POST.get("decision"),
                          request.POST.get("note", ""))
        messages.success(request, "Décision appliquée.")
    except ErreurEconomie as e:
        messages.error(request, str(e))
    return redirect("commande", pk=pk)


@login_required
def litiges(request):
    if not request.user.est_divinite:
        raise PermissionDenied
    ouverts = (Order.objects.filter(statut=S.LITIGE)
               .exclude(Q(acheteur=request.user) | Q(vendeur=request.user))
               .select_related("acheteur", "vendeur", "litige_par")
               .order_by("date_creation"))
    tranches = (Order.objects.filter(tranche_par__isnull=False)
                .select_related("acheteur", "vendeur", "tranche_par")
                .order_by("-date_fin")[:20])
    return render(request, "orders/litiges.html",
                  {"ouverts": ouverts, "tranches": tranches})
