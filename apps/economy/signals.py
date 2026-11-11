import logging

from django.contrib import messages
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .services import bonus_quotidien, empreinte_appareil

logger = logging.getLogger(__name__)


@receiver(user_logged_in)
def donner_bonus(sender, request, user, **kwargs):
    # Un bonus ne doit jamais empecher un membre de se connecter : toute
    # erreur est journalisee et la connexion se poursuit normalement.
    try:
        montant = bonus_quotidien(user, appareil=empreinte_appareil(request))
    except Exception:
        logger.exception("Bonus quotidien non verse (utilisateur %s)", user.pk)
        return
    # request peut ne pas passer par le middleware messages (tests,
    # connexion programmatique) : on n'affiche le message que si possible.
    if montant and request is not None and hasattr(request, "_messages"):
        messages.success(
            request,
            f"Bonus quotidien : +{montant} Cubis 💎 "
            f"(série : {user.serie_connexion} jour(s))")
