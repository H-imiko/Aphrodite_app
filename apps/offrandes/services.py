from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.economy.models import Transaction
from apps.economy.services import ErreurEconomie, _verrouiller
from apps.notifications.services import notifier
from .models import Blocage, Offrande, OffrandeEnvoyee

MAX_PAR_DESTINATAIRE_JOUR = 5
MAX_PAR_JOUR = 30


def envoyer(expediteur, destinataire_id, offrande_id, message="",
            anonyme=False):
    message = (message or "").strip()[:150]
    User = get_user_model()
    if expediteur.est_suspendu:
        raise ErreurEconomie("Ton compte est suspendu.")
    try:
        dest = User.objects.get(pk=destinataire_id, is_active=True)
    except User.DoesNotExist:
        raise ErreurEconomie("Membre introuvable.")
    if dest.pk == expediteur.pk:
        raise ErreurEconomie("Tu ne peux pas t'envoyer une offrande à "
                             "toi-même.")
    if dest.est_suspendu or Blocage.objects.filter(
            bloqueur=dest, bloque=expediteur).exists():
        raise ErreurEconomie("Impossible d'envoyer une offrande à ce membre.")
    try:
        offrande = Offrande.objects.get(pk=offrande_id, est_actif=True)
    except Offrande.DoesNotExist:
        raise ErreurEconomie("Cette offrande n'est plus disponible.")

    depuis = timezone.now() - timedelta(hours=24)
    with transaction.atomic():
        ach = _verrouiller(expediteur)[expediteur.pk]
        recents = OffrandeEnvoyee.objects.filter(
            expediteur=ach, date__gte=depuis)
        if recents.count() >= MAX_PAR_JOUR:
            raise ErreurEconomie(
                f"Limite de {MAX_PAR_JOUR} offrandes par jour atteinte.")
        if recents.filter(destinataire=dest).count() >= MAX_PAR_DESTINATAIRE_JOUR:
            raise ErreurEconomie(
                f"Tu as déjà envoyé {MAX_PAR_DESTINATAIRE_JOUR} offrandes à "
                "ce membre aujourd'hui.")
        prix = offrande.prix_cubis
        paye = 0
        if not ach.est_divinite:
            if ach.solde_cubis < prix:
                raise ErreurEconomie("Solde insuffisant.")
            ach.solde_cubis -= prix
            ach.save(update_fields=["solde_cubis"])
            Transaction.objects.create(
                expediteur=ach, destinataire=None, montant=prix,
                type=Transaction.Type.OFFRANDE,
                description=f"Offrande : {offrande.nom}"[:200])
            paye = prix
        don = OffrandeEnvoyee.objects.create(
            expediteur=ach, destinataire=dest, offrande=offrande,
            message=message, anonyme=bool(anonyme), prix_paye=paye)
        de = "Quelqu'un" if anonyme else ach.pseudo_whatsapp
        notifier(dest, "Tu as reçu une offrande 🌹",
                 f"{de} t'offre « {offrande.nom} »",
                 reverse("offrandes_recues", args=[dest.pk]), "offrande")
    return don


def _don_recu(user, don_id):
    don = (OffrandeEnvoyee.objects.select_related("expediteur")
           .filter(pk=don_id, destinataire=user).first())
    if don is None:
        raise ErreurEconomie("Offrande introuvable.")
    return don


def basculer_masque(user, don_id):
    """Cache (ou réaffiche) une offrande reçue sur son profil."""
    don = _don_recu(user, don_id)
    don.masque = not don.masque
    don.save(update_fields=["masque"])
    return don.masque


def bloquer(user, don_id):
    """Bloque l'expéditeur d'une offrande (même anonyme) et masque ses dons."""
    don = _don_recu(user, don_id)
    with transaction.atomic():
        Blocage.objects.get_or_create(
            bloqueur=user, bloque=don.expediteur,
            defaults={"via_anonyme": don.anonyme})
        OffrandeEnvoyee.objects.filter(
            destinataire=user, expediteur=don.expediteur).update(masque=True)


def debloquer(user, blocage_id):
    supprimes, _ = Blocage.objects.filter(
        pk=blocage_id, bloqueur=user).delete()
    if not supprimes:
        raise ErreurEconomie("Blocage introuvable.")
