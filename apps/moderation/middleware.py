from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from .models import Sanction

PREFIXES_LIBRES = ("/static/", "/media/")


class ModerationMiddleware:
    """Bloque les comptes suspendus et affiche les sanctions non lues."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated and not request.path.startswith(PREFIXES_LIBRES):
            if user.est_suspendu:
                fin = user.date_fin_suspension
                if fin and fin <= timezone.now():
                    user.est_suspendu = False
                    user.date_fin_suspension = None
                    user.save(update_fields=["est_suspendu",
                                             "date_fin_suspension"])
                elif request.path not in (reverse("suspendu"),
                                          reverse("deconnexion")):
                    return redirect("suspendu")
            if not user.est_suspendu:
                non_vues = list(Sanction.objects.filter(user=user, vu=False))
                for s in non_vues:
                    messages.warning(
                        request, f"⚠️ {s.get_type_display()} : {s.raison}")
                if non_vues:
                    Sanction.objects.filter(
                        pk__in=[s.pk for s in non_vues]).update(vu=True)
        return self.get_response(request)
