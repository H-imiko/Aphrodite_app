from datetime import timedelta
from functools import wraps

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from django.shortcuts import render
from django.utils import timezone

from apps.creators.models import Candidature
from apps.economy.models import Transaction
from apps.shop.models import Item
from .models import AuditLog

User = get_user_model()

# Cubis "créés" : ceux qui viennent du Trésor (système) + les achats
# faits par une Divinité (elle ne paie rien, le vendeur reçoit quand même).
CONDITION_EMIS = (
    Q(expediteur__isnull=True)
    | Q(expediteur__est_divinite=True, type=Transaction.Type.ACHAT)
)


def divinite_requise(vue):
    @login_required
    @wraps(vue)
    def enveloppe(request, *args, **kwargs):
        if not request.user.est_divinite:
            raise PermissionDenied
        return vue(request, *args, **kwargs)
    return enveloppe


def _somme(qs):
    return qs.aggregate(t=Sum("montant"))["t"] or 0


def _emis(qs):
    return _somme(qs.filter(CONDITION_EMIS))


def _detruits(qs):
    return _somme(qs.filter(type=Transaction.Type.DESTRUCTION))


@divinite_requise
def panel(request):
    il_y_a_7_jours = timezone.now() - timedelta(days=7)
    return render(request, "moderation/panel.html", {
        "nb_membres": User.objects.filter(is_active=True).count(),
        "nb_nouveaux": User.objects.filter(
            date_inscription__gte=il_y_a_7_jours).count(),
        "nb_createurs": User.objects.filter(createur_valide=True).count(),
        "nb_candidatures": Candidature.objects.filter(
            statut=Candidature.Statut.EN_ATTENTE).count(),
        "nb_articles": Item.objects.filter(est_actif=True).count(),
    })


@divinite_requise
def economie(request):
    maintenant = timezone.now()
    tout = Transaction.objects.all()

    emis = _emis(tout)
    detruits = _detruits(tout)
    detenus = User.objects.aggregate(t=Sum("solde_cubis"))["t"] or 0
    circulation_theorique = emis - detruits

    def periode(jours):
        qs = tout.filter(date__gte=maintenant - timedelta(days=jours))
        return {"jours": jours, "emis": _emis(qs), "detruits": _detruits(qs)}

    avant = tout.filter(date__lt=maintenant - timedelta(days=30))
    circulation_avant = _emis(avant) - _detruits(avant)
    croissance = None
    if circulation_avant > 0:
        croissance = round(
            (circulation_theorique - circulation_avant) * 100
            / circulation_avant)

    noms_types = dict(Transaction.Type.choices)
    mouvements = [
        {"nom": noms_types.get(ligne["type"], ligne["type"]),
         "total": ligne["total"], "nb": ligne["nb"]}
        for ligne in (
            tout.filter(date__gte=maintenant - timedelta(days=30))
            .values("type")
            .annotate(total=Sum("montant"), nb=Count("id"))
            .order_by("-total"))
    ]

    return render(request, "moderation/economie.html", {
        "circulation": detenus,
        "emis": emis,
        "detruits": detruits,
        "croissance": croissance,
        "alerte": croissance is not None and croissance > 20,
        "periodes": [periode(7), periode(30)],
        "mouvements": mouvements,
        "ecart": detenus - circulation_theorique,
        "top": User.objects.filter(est_divinite=False)
                           .order_by("-solde_cubis")[:5],
    })


@divinite_requise
def journal(request):
    logs = AuditLog.objects.select_related("auteur", "cible")[:200]
    return render(request, "moderation/journal.html", {"logs": logs})