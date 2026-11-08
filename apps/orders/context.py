from django.db.models import Q


def commandes_a_traiter(request):
    """Pastilles du menu : commandes à traiter et notifications non lues."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    from apps.notifications.models import Notification
    from .models import Order
    S = Order.Statut
    n = Order.objects.filter(vendeur=user, statut=S.DEMANDE).count()
    n += Order.objects.filter(acheteur=user, statut=S.LIVREE).count()
    if user.est_divinite:
        n += Order.objects.filter(statut=S.LITIGE).exclude(
            Q(acheteur=user) | Q(vendeur=user)).count()
    return {
        "nb_commandes_a_traiter": n,
        "nb_notifications": Notification.objects.filter(
            user=user, lu=False).count(),
    }
