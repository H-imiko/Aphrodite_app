from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.creators.models import Candidature
from apps.economy.models import Transaction
from apps.orders.models import Order
from apps.shop.models import Item
from . import sanctions
from .models import AuditLog, Report
from .sanctions import ErreurModeration

User = get_user_model()
T = Transaction.Type

# Cubis "créés" : ceux qui viennent du Trésor + les achats faits par une
# Divinité. Les paiements et remboursements de commandes ne créent rien :
# ils redonnent des Cubis déjà bloqués.
CONDITION_EMIS = (
    (Q(expediteur__isnull=True) & ~Q(type__in=[T.LIBERATION, T.REMBOURSEMENT]))
    | Q(expediteur__est_divinite=True, type=T.ACHAT)
)
# Cubis "détruits" : achats officiels + sanctions.
CONDITION_DETRUITS = Q(type__in=[T.DESTRUCTION, T.SANCTION, T.OFFRANDE])


def divinite_requise(vue):
    @login_required
    @wraps(vue)
    def enveloppe(request, *args, **kwargs):
        if not request.user.est_divinite:
            raise PermissionDenied
        return vue(request, *args, **kwargs)
    return enveloppe


def moderation_requise(vue):
    """Divinité ou membre du staff : accès aux outils de modération."""
    @login_required
    @wraps(vue)
    def enveloppe(request, *args, **kwargs):
        if not (request.user.est_divinite or request.user.is_staff):
            raise PermissionDenied
        return vue(request, *args, **kwargs)
    return enveloppe


def _somme(qs):
    return qs.aggregate(t=Sum("montant"))["t"] or 0


def _emis(qs):
    return _somme(qs.filter(CONDITION_EMIS))


def _detruits(qs):
    return _somme(qs.filter(CONDITION_DETRUITS))


def _entier(valeur):
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return 0


@moderation_requise
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
        "nb_signalements": Report.objects.filter(
            statut=Report.Statut.OUVERT).count(),
        "nb_litiges": Order.objects.filter(
            statut=Order.Statut.LITIGE).count(),
    })


@divinite_requise
def economie(request):
    maintenant = timezone.now()
    tout = Transaction.objects.all()

    emis = _emis(tout)
    detruits = _detruits(tout)
    detenus = User.objects.aggregate(t=Sum("solde_cubis"))["t"] or 0
    bloques = Order.objects.filter(statut__in=[
        Order.Statut.EN_COURS, Order.Statut.LIVREE, Order.Statut.LITIGE]
    ).aggregate(t=Sum("prix_cubis"))["t"] or 0
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
        "bloques": bloques,
        "emis": emis,
        "detruits": detruits,
        "croissance": croissance,
        "alerte": croissance is not None and croissance > 20,
        "periodes": [periode(7), periode(30)],
        "mouvements": mouvements,
        "ecart": detenus + bloques - circulation_theorique,
        "top": User.objects.filter(est_divinite=False)
                           .order_by("-solde_cubis")[:5],
    })


@divinite_requise
def journal(request):
    logs = AuditLog.objects.select_related("auteur", "cible")[:200]
    return render(request, "moderation/journal.html", {"logs": logs})


@moderation_requise
def signalements(request):
    ouverts = (Report.objects.filter(statut=Report.Statut.OUVERT)
               .select_related("auteur", "article", "membre")
               .order_by("date"))
    traites = (Report.objects.exclude(statut=Report.Statut.OUVERT)
               .select_related("auteur", "article", "membre", "traite_par")
               .order_by("-date_traitement")[:20])
    return render(request, "moderation/signalements.html",
                  {"ouverts": ouverts, "traites": traites})


@moderation_requise
def signalement(request, pk):
    r = get_object_or_404(
        Report.objects.select_related("auteur", "article",
                                      "article__createur", "membre",
                                      "traite_par"), pk=pk)
    cible = r.article.createur if r.article_id else r.membre
    return render(request, "moderation/signalement.html",
                  {"r": r, "cible": cible})


@moderation_requise
@require_POST
def signalement_action(request, pk):
    action = request.POST.get("action")
    try:
        if action == "masquer":
            sanctions.masquer_article(request.user, pk)
            messages.success(request, "Article masqué, signalement clos.")
        elif action == "classer":
            sanctions.classer(request.user, pk)
            messages.success(request, "Signalement classé sans suite.")
        else:
            raise ErreurModeration("Action inconnue.")
    except ErreurModeration as e:
        messages.error(request, str(e))
    return redirect("signalements")


@moderation_requise
def membre_moderation(request, pk):
    cible = get_object_or_404(User, pk=pk)
    sig = request.GET.get("signalement")
    signalement_lie = (Report.objects.filter(pk=sig).first()
                       if sig and sig.isdigit() else None)
    protege = (cible.pk == request.user.pk or cible.is_superuser
               or (cible.est_divinite and not request.user.is_superuser)
               # un modérateur n'agit pas sur un autre modérateur
               or (cible.is_staff and not request.user.est_divinite))
    return render(request, "moderation/membre.html", {
        "cible": cible,
        "sanctions": cible.sanctions.select_related("par")[:30],
        "signalement": signalement_lie,
        "nb_signalements": cible.signalements_recus.filter(
            statut=Report.Statut.OUVERT).count(),
        "offrandes_recues": cible.offrandes_recues.select_related(
            "expediteur", "offrande")[:20],
        "peut_decider": request.user.is_superuser,
        "protege": protege,
        "durees": sanctions.DUREES,
    })


@moderation_requise
@require_POST
def sanction_action(request, pk):
    cible = get_object_or_404(User, pk=pk)
    action = request.POST.get("action")
    raison = request.POST.get("raison", "")
    sig_id = _entier(request.POST.get("signalement")) or None
    try:
        if action == "avertir":
            sanctions.avertir(request.user, cible, raison, sig_id)
            messages.success(request, "Avertissement envoyé.")
        elif action == "suspendre":
            sanctions.suspendre(request.user, cible,
                                _entier(request.POST.get("jours")),
                                raison, sig_id)
            messages.success(request, "Compte suspendu.")
        elif action == "lever":
            sanctions.lever_suspension(request.user, cible)
            messages.success(request, "Suspension levée.")
        elif action == "retirer_createur":
            sanctions.retirer_createur(request.user, cible, raison, sig_id)
            messages.success(
                request, "Statut Créateur retiré, articles masqués.")
        elif action == "reduire":
            sanctions.reduire_cubis(request.user, cible,
                                    _entier(request.POST.get("montant")),
                                    raison, sig_id)
            messages.success(request, "Cubis retirés.")
        else:
            raise ErreurModeration("Action inconnue.")
    except ErreurModeration as e:
        messages.error(request, str(e))
    url = reverse("membre_moderation", args=[cible.pk])
    if sig_id:
        url += f"?signalement={sig_id}"
    return redirect(url)


# ----- Rôles : nommer des Divinités et des modérateurs -----

# action -> (champ du compte, valeur, nom du rôle)
ROLES = {
    "divinite": ("est_divinite", True, "Divinité"),
    "retirer_divinite": ("est_divinite", False, "Divinité"),
    "staff": ("is_staff", True, "Modérateur"),
    "retirer_staff": ("is_staff", False, "Modérateur"),
}


@divinite_requise
def equipe(request):
    recherche = request.GET.get("q", "").strip()
    membres = User.objects.filter(is_active=True).order_by(
        "-est_divinite", "-is_staff", "pseudo_whatsapp")
    if recherche:
        membres = membres.filter(Q(pseudo_whatsapp__icontains=recherche)
                                 | Q(email__icontains=recherche))
    return render(request, "moderation/equipe.html", {
        "membres": membres[:100],
        "total": membres.count(),
        "q": recherche,
        "nb_divinites": User.objects.filter(est_divinite=True,
                                            is_active=True).count(),
        "nb_staff": User.objects.filter(is_staff=True,
                                        is_active=True).count(),
    })


@divinite_requise
@require_POST
def equipe_action(request, pk):
    cible = get_object_or_404(User, pk=pk)
    action = request.POST.get("action", "")
    if action not in ROLES:
        messages.error(request, "Action inconnue.")
        return redirect("equipe")
    if cible.is_superuser:
        messages.error(request,
                       "Le compte de la propriétaire ne se modifie pas ici.")
        return redirect("equipe")
    if cible.pk == request.user.pk:
        messages.error(request, "Tu ne peux pas modifier tes propres rôles : "
                                "demande-le à une autre Divinité.")
        return redirect("equipe")
    champ, valeur, libelle = ROLES[action]
    if (champ == "est_divinite" and not valeur
            and not User.objects.filter(est_divinite=True)
                                .exclude(pk=cible.pk).exists()):
        messages.error(request, "Il doit rester au moins une Divinité.")
        return redirect("equipe")
    setattr(cible, champ, valeur)
    cible.save(update_fields=[champ])
    AuditLog.objects.create(
        auteur=request.user,
        action=(AuditLog.Action.ROLE_ATTRIBUE if valeur
                else AuditLog.Action.ROLE_RETIRE),
        cible=cible,
        details=f"{libelle} · {cible.pseudo_whatsapp}")
    messages.success(
        request,
        f"{libelle} {'attribué à' if valeur else 'retiré à'} "
        f"{cible.pseudo_whatsapp}.")
    return redirect("equipe")
