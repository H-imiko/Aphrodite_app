from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from apps.economy.services import ErreurEconomie
from apps.notifications.models import Notification
from apps.notifications.services import notifier
from .models import Abonnement, Like

MAX_NOTIFIES = 2000


def basculer_abonnement(user, createur_id):
    """S'abonner ou se désabonner. Renvoie True si on est abonné ensuite."""
    User = get_user_model()
    try:
        createur = User.objects.get(pk=createur_id, is_active=True)
    except User.DoesNotExist:
        raise ErreurEconomie("Membre introuvable.")
    if createur.pk == user.pk:
        raise ErreurEconomie("Tu ne peux pas t'abonner à toi-même.")
    if not createur.peut_publier:
        raise ErreurEconomie("Tu ne peux t'abonner qu'aux Créateurs.")
    existant = Abonnement.objects.filter(abonne=user, createur=createur)
    if existant.exists():
        existant.delete()
        return False
    try:
        with transaction.atomic():
            Abonnement.objects.create(abonne=user, createur=createur)
    except IntegrityError:
        return True
    lien = reverse("membre", args=[user.pk])
    deja_prevenu = Notification.objects.filter(
        user=createur, type="abonne", lien=lien,
        date__gte=timezone.now() - timedelta(days=7)).exists()
    if not deja_prevenu:
        notifier(createur, "Nouvel abonné",
                 f"{user.pseudo_whatsapp} s'est abonné à toi", lien, "abonne")
    return True


def basculer_like(user, item_id):
    """Aimer ou ne plus aimer un article. Renvoie True si aimé ensuite."""
    from apps.shop.models import Item
    try:
        item = Item.objects.get(pk=item_id)
    except Item.DoesNotExist:
        raise ErreurEconomie("Article introuvable.")
    if item.createur_id == user.pk:
        raise ErreurEconomie("Tu ne peux pas aimer ton propre article.")
    if not item.est_actif:
        raise ErreurEconomie("Cet article n'est pas disponible.")
    existant = Like.objects.filter(user=user, item=item)
    if existant.exists():
        existant.delete()
        return False
    try:
        with transaction.atomic():
            Like.objects.create(user=user, item=item)
    except IntegrityError:
        pass
    return True


def notifier_abonnes(createur, item):
    """Prévient les abonnés d'un Créateur qu'un nouvel article est publié."""
    ids = list(Abonnement.objects.filter(createur=createur)
               .values_list("abonne_id", flat=True)[:MAX_NOTIFIES])
    if not ids:
        return
    lien = reverse("article", args=[item.pk])
    Notification.objects.bulk_create([
        Notification(
            user_id=uid, titre="Nouvel article",
            message=f"{createur.pseudo_whatsapp} a publié « {item.titre} »"[:300],
            lien=lien, type="nouveaute")
        for uid in ids])
