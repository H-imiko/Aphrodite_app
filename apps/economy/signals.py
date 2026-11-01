from django.contrib import messages
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .services import bonus_quotidien


@receiver(user_logged_in)
def donner_bonus(sender, request, user, **kwargs):
    montant = bonus_quotidien(user)
    if montant and request is not None:
        messages.success(
            request,
            f"Bonus quotidien : +{montant} Cubis <img class="cb" src="/static/images/cube_cubis.svg" alt="Cubis"> "
            f"(série : {user.serie_connexion} jour(s))")