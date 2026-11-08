from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Notification


def notifier(user, titre, message="", lien="", type="info", regrouper=False):
    """Crée une notification. Avec regrouper=True, une notification non lue
    identique (même lien et même type) est simplement mise à jour."""
    if user is None:
        return
    titre = titre[:120]
    message = (message or "")[:300]
    if regrouper and lien:
        existante = Notification.objects.filter(
            user=user, lu=False, type=type, lien=lien).first()
        if existante:
            Notification.objects.filter(pk=existante.pk).update(
                titre=titre, message=message, date=timezone.now())
            return
    Notification.objects.create(
        user=user, titre=titre, message=message, lien=lien, type=type)


def notifier_divinites(titre, message="", lien="", type="info", exclure=()):
    User = get_user_model()
    for d in User.objects.filter(est_divinite=True, is_active=True).exclude(
            pk__in=list(exclure)):
        notifier(d, titre, message, lien, type)
