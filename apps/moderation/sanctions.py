from datetime import timedelta

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.economy.models import Transaction
from apps.economy.services import _verrouiller
from apps.notifications.services import notifier
from apps.shop.models import Item
from .models import AuditLog, Report, Sanction
from .services import journaliser

DUREES = (7, 15, 30)


class ErreurModeration(Exception):
    pass


def _divinite(acteur):
    if not acteur.est_divinite:
        raise ErreurModeration("Réservé aux Divinités.")


def _safir(acteur):
    if not acteur.is_superuser:
        raise ErreurModeration("Décision réservée à Safir.")


def _verifier(acteur, cible):
    _divinite(acteur)
    if acteur.pk == cible.pk:
        raise ErreurModeration("Tu ne peux pas te sanctionner toi-même.")
    if cible.is_superuser:
        raise ErreurModeration("La propriétaire ne peut pas être sanctionnée.")
    if cible.est_divinite and not acteur.is_superuser:
        raise ErreurModeration("Seule Safir peut agir sur une Divinité.")


def _raison(raison):
    raison = (raison or "").strip()
    if len(raison) < 3:
        raise ErreurModeration("Indique une raison (3 caractères minimum).")
    return raison[:300]


def _clore(signalement_id, acteur):
    if signalement_id:
        Report.objects.filter(
            pk=signalement_id, statut=Report.Statut.OUVERT
        ).update(statut=Report.Statut.TRAITE, traite_par=acteur,
                 date_traitement=timezone.now())


def avertir(acteur, cible, raison, signalement_id=None):
    _verifier(acteur, cible)
    raison = _raison(raison)
    with transaction.atomic():
        Sanction.objects.create(
            user=cible, type=Sanction.Type.AVERTISSEMENT, raison=raison,
            par=acteur, signalement_id=signalement_id)
        journaliser(acteur, AuditLog.Action.AVERTISSEMENT, cible, raison)
        notifier(cible, "Avertissement", raison,
                 reverse("membre", args=[cible.pk]), "moderation")
        _clore(signalement_id, acteur)


def suspendre(acteur, cible, jours, raison, signalement_id=None):
    _verifier(acteur, cible)
    raison = _raison(raison)
    if jours not in DUREES:
        raise ErreurModeration("Durée invalide (7, 15 ou 30 jours).")
    with transaction.atomic():
        cible.est_suspendu = True
        cible.date_fin_suspension = timezone.now() + timedelta(days=jours)
        cible.save(update_fields=["est_suspendu", "date_fin_suspension"])
        Sanction.objects.create(
            user=cible, type=Sanction.Type.SUSPENSION, raison=raison,
            duree_jours=jours, par=acteur, signalement_id=signalement_id,
            vu=True)
        journaliser(acteur, AuditLog.Action.SUSPENSION, cible,
                    f"{jours} jours · {raison}")
        _clore(signalement_id, acteur)


def lever_suspension(acteur, cible):
    _verifier(acteur, cible)
    if not cible.est_suspendu:
        raise ErreurModeration("Ce compte n'est pas suspendu.")
    with transaction.atomic():
        cible.est_suspendu = False
        cible.date_fin_suspension = None
        cible.save(update_fields=["est_suspendu", "date_fin_suspension"])
        journaliser(acteur, AuditLog.Action.FIN_SUSPENSION, cible, "")


def retirer_createur(acteur, cible, raison, signalement_id=None):
    _verifier(acteur, cible)
    _safir(acteur)
    raison = _raison(raison)
    with transaction.atomic():
        cible.createur_valide = False
        cible.type_compte = "participant"
        cible.save(update_fields=["createur_valide", "type_compte"])
        nb = Item.objects.filter(createur=cible, est_actif=True).update(
            est_actif=False, masque_moderation=True)
        Sanction.objects.create(
            user=cible, type=Sanction.Type.RETRAIT_CREATEUR, raison=raison,
            par=acteur, signalement_id=signalement_id)
        journaliser(acteur, AuditLog.Action.RETRAIT_CREATEUR, cible,
                    f"{nb} article(s) masqué(s) · {raison}")
        notifier(cible, "Statut Créateur retiré", raison,
                 reverse("membre", args=[cible.pk]), "moderation")
        _clore(signalement_id, acteur)


def reduire_cubis(acteur, cible, montant, raison, signalement_id=None):
    _verifier(acteur, cible)
    _safir(acteur)
    raison = _raison(raison)
    if montant <= 0:
        raise ErreurModeration("Le montant doit être positif.")
    with transaction.atomic():
        u = _verrouiller(cible)[cible.pk]
        if montant > u.solde_cubis:
            raise ErreurModeration(
                f"Solde insuffisant : {u.solde_cubis} Cubis.")
        u.solde_cubis -= montant
        u.save(update_fields=["solde_cubis"])
        Transaction.objects.create(
            expediteur=u, destinataire=None, montant=montant,
            type=Transaction.Type.SANCTION, description=raison[:200])
        Sanction.objects.create(
            user=u, type=Sanction.Type.REDUCTION_CUBIS, raison=raison,
            montant=montant, par=acteur, signalement_id=signalement_id)
        journaliser(acteur, AuditLog.Action.REDUCTION_CUBIS, u,
                    f"-{montant} Cubis · {raison}")
        notifier(u, "Réduction de Cubis", f"-{montant} Cubis : {raison}",
                 reverse("transactions"), "moderation")
        _clore(signalement_id, acteur)


def masquer_article(acteur, signalement_id):
    _divinite(acteur)
    with transaction.atomic():
        try:
            r = Report.objects.select_for_update().get(pk=signalement_id)
        except Report.DoesNotExist:
            raise ErreurModeration("Signalement introuvable.")
        if r.statut != Report.Statut.OUVERT:
            raise ErreurModeration("Ce signalement est déjà traité.")
        article = r.article
        if article is None:
            raise ErreurModeration("Ce signalement ne concerne pas un article.")
        article.est_actif = False
        article.masque_moderation = True
        article.save(update_fields=["est_actif", "masque_moderation"])
        r.statut = Report.Statut.TRAITE
        r.traite_par = acteur
        r.date_traitement = timezone.now()
        r.save()
        journaliser(acteur, AuditLog.Action.ARTICLE_MASQUE, article.createur,
                    f"{article.titre} (signalement #{r.pk})")
        notifier(article.createur, "Article masqué",
                 f"« {article.titre} » a été masqué par la modération.",
                 reverse("mes_articles"), "moderation")


def classer(acteur, signalement_id):
    _divinite(acteur)
    with transaction.atomic():
        try:
            r = Report.objects.select_for_update().get(pk=signalement_id)
        except Report.DoesNotExist:
            raise ErreurModeration("Signalement introuvable.")
        if r.statut != Report.Statut.OUVERT:
            raise ErreurModeration("Ce signalement est déjà traité.")
        r.statut = Report.Statut.CLASSE
        r.traite_par = acteur
        r.date_traitement = timezone.now()
        r.save()
        journaliser(acteur, AuditLog.Action.SIGNALEMENT_CLASSE, None,
                    f"Signalement #{r.pk} ({r.get_motif_display()})")
