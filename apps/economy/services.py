import random
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.moderation.models import AuditLog
from apps.moderation.services import journaliser
from .models import Transaction


class ErreurEconomie(Exception):
    pass


def _verrouiller(*users):
    """Verrouille les lignes en base (toujours dans le même ordre)."""
    User = get_user_model()
    ids = sorted({u.pk for u in users})
    qs = User.objects.select_for_update().filter(pk__in=ids).order_by("pk")
    return {u.pk: u for u in qs}


def bonus_quotidien(user):
    """Donne le bonus du jour. Renvoie le montant, ou None si déjà reçu."""
    with transaction.atomic():
        u = _verrouiller(user)[user.pk]
        aujourdhui = timezone.localdate()
        if u.derniere_connexion_bonus == aujourdhui:
            return None
        hier = aujourdhui - timedelta(days=1)
        if u.derniere_connexion_bonus == hier:
            u.serie_connexion += 1
        else:
            u.serie_connexion = 1
        bonus_serie = min(u.serie_connexion - 1, 7) * 2
        montant = random.randint(15, 25) + bonus_serie
        u.solde_cubis += montant
        u.derniere_connexion_bonus = aujourdhui
        u.save(update_fields=["solde_cubis", "serie_connexion",
                              "derniere_connexion_bonus"])
        Transaction.objects.create(
            destinataire=u, montant=montant,
            type=Transaction.Type.CONNEXION,
            description=f"Série de {u.serie_connexion} jour(s)")
    user.refresh_from_db()
    return montant


def envoyer_par_divinite(divinite, destinataire, montant, description=""):
    """Envoi depuis le Trésor : illimité pour Safir, plafonné pour les Gardiennes."""
    if not divinite.est_divinite:
        raise ErreurEconomie("Seules les Divinités peuvent utiliser le Trésor.")
    if montant <= 0:
        raise ErreurEconomie("Le montant doit être positif.")
    if not divinite.is_superuser and montant > settings.LIMITE_ENVOI_GARDIENNE:
        raise ErreurEconomie(
            f"Limite par envoi : {settings.LIMITE_ENVOI_GARDIENNE} Cubis.")
    with transaction.atomic():
        d = _verrouiller(destinataire)[destinataire.pk]
        d.solde_cubis += montant
        d.save(update_fields=["solde_cubis"])
        Transaction.objects.create(
            expediteur=None, auteur=divinite, destinataire=d,
            montant=montant, type=Transaction.Type.ENVOI_DIVINITE,
            description=description)
        details = f"{montant} Cubis"
        if description:
            details += f" · {description}"
        journaliser(divinite, AuditLog.Action.ENVOI_CUBIS, d, details)


def transferer(expediteur, destinataire, montant, description=""):
    """Transfert entre membres."""
    if montant <= 0:
        raise ErreurEconomie("Le montant doit être positif.")
    if expediteur.pk == destinataire.pk:
        raise ErreurEconomie("Tu ne peux pas t'envoyer des Cubis à toi-même.")
    if expediteur.est_suspendu:
        raise ErreurEconomie("Ton compte est suspendu.")
    with transaction.atomic():
        verrous = _verrouiller(expediteur, destinataire)
        exp = verrous[expediteur.pk]
        dest = verrous[destinataire.pk]
        if exp.solde_cubis < montant:
            raise ErreurEconomie("Solde insuffisant.")
        exp.solde_cubis -= montant
        dest.solde_cubis += montant
        exp.save(update_fields=["solde_cubis"])
        dest.save(update_fields=["solde_cubis"])
        Transaction.objects.create(
            expediteur=exp, destinataire=dest, montant=montant,
            type=Transaction.Type.TRANSFERT, description=description)