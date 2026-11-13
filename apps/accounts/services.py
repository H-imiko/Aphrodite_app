from django.db import transaction
from django.db.models import Q

from apps.notifications.models import Notification
from apps.orders.models import Order
from .models import DemandeAcces
from apps.shop.models import Item
from apps.social.models import Abonnement, Like

# Une commande dans ces états bloque encore des Cubis (séquestre) ou une
# décision : fermer le compte laisserait l'acheteur sans recours.
STATUTS_BLOQUANTS = (Order.Statut.DEMANDE, Order.Statut.EN_COURS,
                     Order.Statut.LITIGE)


class SuppressionRefusee(Exception):
    """Le compte ne peut pas être fermé tant qu'une commande est en cours."""


def commandes_bloquantes(user):
    return (Order.objects.filter(Q(acheteur=user) | Q(vendeur=user),
                                 statut__in=STATUTS_BLOQUANTS)
            .order_by("-date_creation"))


@transaction.atomic
def fermer_compte(user):
    """Efface les données personnelles du compte et le ferme définitivement.

    Les commandes et les transactions restent en base : elles appartiennent
    aussi à d'autres membres et servent de preuve en cas de litige. Tout ce
    qui identifie la personne est effacé, l'email est libéré, les articles
    sont retirés de la vente et les fichiers personnels supprimés.
    """
    en_cours = commandes_bloquantes(user).count()
    if en_cours:
        raise SuppressionRefusee(
            f"Tu as {en_cours} commande{'s' if en_cours > 1 else ''} en cours : "
            "termine-la ou annule-la avant de supprimer ton compte, sinon les "
            "Cubis bloqués restent bloqués.")

    # Les demandes d'acces contiennent l'adresse email du membre.
    DemandeAcces.objects.filter(email__iexact=user.email).delete()
    Item.objects.filter(createur=user).update(est_actif=False)
    Abonnement.objects.filter(abonne=user).delete()
    Abonnement.objects.filter(createur=user).delete()
    Like.objects.filter(user=user).delete()
    Notification.objects.filter(user=user).delete()

    for champ in ("avatar", "banniere"):
        fichier = getattr(user, champ)
        if fichier:
            fichier.delete(save=False)

    ancien_pk = user.pk
    user.email = f"supprime-{ancien_pk}@supprime.invalid"
    user.pseudo_whatsapp = "Compte supprimé"
    user.bio_rp = ""
    user.numero_whatsapp = ""
    user.titre = ""
    user.date_naissance = None
    user.avatar = None
    user.banniere = None
    user.solde_cubis = 0
    user.serie_connexion = 0
    user.profil_mature = False
    user.afficher_mature = False
    user.is_active = False
    user.est_suspendu = True
    user.set_unusable_password()
    user.save()
    return user
