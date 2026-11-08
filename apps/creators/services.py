from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.economy.models import Transaction
from apps.economy.services import ErreurEconomie, _verrouiller
from apps.moderation.models import AuditLog
from apps.moderation.services import journaliser
from apps.notifications.services import notifier
from .models import Candidature


def valider(candidature_id, divinite):
    if not divinite.est_divinite:
        raise ErreurEconomie("Réservé aux Divinités.")
    with transaction.atomic():
        c = Candidature.objects.select_for_update().get(pk=candidature_id)
        if c.statut != Candidature.Statut.EN_ATTENTE:
            raise ErreurEconomie("Cette candidature a déjà été traitée.")
        u = _verrouiller(c.user)[c.user_id]
        u.createur_valide = True
        u.type_compte = "createur"
        deja_paye = Transaction.objects.filter(
            destinataire=u, type=Transaction.Type.BONUS_CREATEUR).exists()
        if not deja_paye:
            u.solde_cubis += settings.BONUS_CREATEUR
            Transaction.objects.create(
                expediteur=None, auteur=divinite, destinataire=u,
                montant=settings.BONUS_CREATEUR,
                type=Transaction.Type.BONUS_CREATEUR,
                description="Bonus de validation Créateur")
        u.save(update_fields=["createur_valide", "type_compte", "solde_cubis"])
        c.statut = Candidature.Statut.VALIDEE
        c.traitee_par = divinite
        c.date_traitement = timezone.now()
        c.save()
        details = ("Bonus déjà versé auparavant" if deja_paye
                   else f"+{settings.BONUS_CREATEUR} Cubis")
        journaliser(divinite, AuditLog.Action.CANDIDATURE_VALIDEE, u, details)
        notifier(u, "Candidature validée 🎉",
                 "Tu es maintenant Créateur : tu peux publier des articles."
                 + ("" if deja_paye
                    else f" +{settings.BONUS_CREATEUR} Cubis de bienvenue !"),
                 reverse("mes_articles"), "createur")


def refuser(candidature_id, divinite, motif=""):
    if not divinite.est_divinite:
        raise ErreurEconomie("Réservé aux Divinités.")
    with transaction.atomic():
        c = Candidature.objects.select_for_update().get(pk=candidature_id)
        if c.statut != Candidature.Statut.EN_ATTENTE:
            raise ErreurEconomie("Cette candidature a déjà été traitée.")
        c.statut = Candidature.Statut.REFUSEE
        c.motif_refus = motif
        c.traitee_par = divinite
        c.date_traitement = timezone.now()
        c.save()
        journaliser(divinite, AuditLog.Action.CANDIDATURE_REFUSEE,
                    c.user, motif)
        notifier(c.user, "Candidature refusée",
                 motif or "Tu peux en envoyer une nouvelle.",
                 reverse("postuler"), "createur")
