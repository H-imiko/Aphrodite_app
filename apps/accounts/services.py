from django.db import transaction

from apps.notifications.models import Notification
from apps.shop.models import Item
from apps.social.models import Abonnement, Like


@transaction.atomic
def fermer_compte(user):
    """Efface les données personnelles du compte et le ferme définitivement.

    Les commandes et les transactions restent en base : elles appartiennent
    aussi à d'autres membres et servent de preuve en cas de litige. Tout ce
    qui identifie la personne est effacé, l'email est libéré, les articles
    sont retirés de la vente et les fichiers personnels supprimés.
    """
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
