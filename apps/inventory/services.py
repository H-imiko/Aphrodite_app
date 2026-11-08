from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.economy.services import ErreurEconomie
from apps.notifications.services import notifier
from .models import Equipement, InventoryItem, ObjectTransfer

S = ObjectTransfer.Statut
MAX_EN_ATTENTE = 20
DELAI_JOURS = 14


def offrir(expediteur, destinataire_id, item_id, message=""):
    message = (message or "").strip()[:200]
    User = get_user_model()
    if expediteur.est_suspendu:
        raise ErreurEconomie("Ton compte est suspendu.")
    try:
        dest = User.objects.get(pk=destinataire_id, is_active=True)
    except User.DoesNotExist:
        raise ErreurEconomie("Destinataire introuvable.")
    if dest.pk == expediteur.pk:
        raise ErreurEconomie("Tu ne peux pas t'offrir un objet à toi-même.")
    if dest.est_suspendu:
        raise ErreurEconomie("Ce membre ne peut pas recevoir de cadeau "
                             "pour le moment.")
    with transaction.atomic():
        possession = (InventoryItem.objects.select_for_update()
                      .select_related("item")
                      .filter(proprietaire=expediteur, item_id=item_id)
                      .first())
        if possession is None:
            raise ErreurEconomie("Tu ne possèdes pas cet objet.")
        item = possession.item
        if InventoryItem.objects.filter(proprietaire=dest, item=item).exists():
            raise ErreurEconomie("Ce membre possède déjà cet objet.")
        if ObjectTransfer.objects.filter(
                expediteur=expediteur, item=item, statut=S.ENVOYE).exists():
            raise ErreurEconomie("Cet objet est déjà proposé en cadeau.")
        if ObjectTransfer.objects.filter(
                expediteur=expediteur, statut=S.ENVOYE
        ).count() >= MAX_EN_ATTENTE:
            raise ErreurEconomie(
                f"Tu as déjà {MAX_EN_ATTENTE} cadeaux en attente.")
        t = ObjectTransfer.objects.create(
            expediteur=expediteur, destinataire=dest, item=item,
            message=message)
        notifier(dest, "Un cadeau t'attend 🎁",
                 f"{expediteur.pseudo_whatsapp} t'offre « {item.titre} »",
                 reverse("cadeaux"), "cadeau")
    return t


def _charger(transfer_id):
    try:
        return (ObjectTransfer.objects.select_for_update()
                .select_related("expediteur", "destinataire", "item")
                .get(pk=transfer_id))
    except ObjectTransfer.DoesNotExist:
        raise ErreurEconomie("Cadeau introuvable.")


def accepter(user, transfer_id):
    erreur = None
    with transaction.atomic():
        t = _charger(transfer_id)
        if t.destinataire_id != user.pk:
            raise ErreurEconomie("Ce cadeau n'est pas pour toi.")
        if t.statut != S.ENVOYE:
            raise ErreurEconomie("Ce cadeau n'est plus disponible.")
        if user.est_suspendu:
            raise ErreurEconomie("Ton compte est suspendu.")
        maintenant = timezone.now()
        possession = (InventoryItem.objects.select_for_update()
                      .filter(proprietaire_id=t.expediteur_id,
                              item_id=t.item_id).first())
        if possession is None:
            t.statut = S.ANNULE
            t.date_reponse = maintenant
            t.save()
            erreur = "L'expéditeur ne possède plus cet objet."
        elif InventoryItem.objects.filter(
                proprietaire=user, item_id=t.item_id).exists():
            t.statut = S.ANNULE
            t.date_reponse = maintenant
            t.save()
            erreur = "Tu possèdes déjà cet objet."
        else:
            est_relique = possession.est_relique
            possession.delete()
            InventoryItem.objects.create(
                proprietaire=user, item_id=t.item_id, est_relique=est_relique)
            # l'ancien propriétaire ne l'affiche plus sur son profil
            Equipement.objects.filter(
                user_id=t.expediteur_id, cadre_id=t.item_id).update(cadre=None)
            Equipement.objects.filter(
                user_id=t.expediteur_id, decor_id=t.item_id).update(decor=None)
            t.statut = S.ACCEPTE
            t.date_reponse = maintenant
            t.save()
            notifier(t.expediteur, "Cadeau accepté 🎁",
                     f"{user.pseudo_whatsapp} a accepté « {t.item.titre} »",
                     reverse("cadeaux"), "cadeau")
    if erreur:
        raise ErreurEconomie(erreur)


def refuser(user, transfer_id):
    with transaction.atomic():
        t = _charger(transfer_id)
        if t.destinataire_id != user.pk:
            raise ErreurEconomie("Ce cadeau n'est pas pour toi.")
        if t.statut != S.ENVOYE:
            raise ErreurEconomie("Ce cadeau n'est plus disponible.")
        t.statut = S.REFUSE
        t.date_reponse = timezone.now()
        t.save()
        notifier(t.expediteur, "Cadeau refusé",
                 f"{user.pseudo_whatsapp} a refusé « {t.item.titre} »",
                 reverse("cadeaux"), "cadeau")


def annuler(user, transfer_id):
    with transaction.atomic():
        t = _charger(transfer_id)
        if t.expediteur_id != user.pk:
            raise ErreurEconomie("Ce cadeau n'est pas le tien.")
        if t.statut != S.ENVOYE:
            raise ErreurEconomie("Ce cadeau n'est plus en attente.")
        t.statut = S.ANNULE
        t.date_reponse = timezone.now()
        t.save()


def traiter_echeances():
    """Les cadeaux sans réponse expirent après quelques jours."""
    limite = timezone.now() - timedelta(days=DELAI_JOURS)
    ObjectTransfer.objects.filter(statut=S.ENVOYE, date__lte=limite).update(
        statut=S.EXPIRE, date_reponse=timezone.now())
