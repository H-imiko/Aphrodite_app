from django.contrib import messages
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .services import bonus_quotidien, empreinte_appareil


@receiver(user_logged_in)
def donner_bonus(sender, request, user, **kwargs):
    montant = bonus_quotidien(user, appareil=empreinte_appareil(request))
    # request peut ne pas passer par le middleware messages (tests,
    # connexion programmatique) : on n'affiche le message que si possible.
    if montant and request is not None and hasattr(request, "_messages"):
        messages.success(
            request,
            f"Bonus quotidien : +{montant} Cubis 💎 "
            f"(série : {user.serie_connexion} jour(s))")