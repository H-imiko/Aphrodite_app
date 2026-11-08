from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Notification


@login_required
def liste(request):
    notifs = list(Notification.objects.filter(user=request.user)[:60])
    non_lues = [n.pk for n in notifs if not n.lu]
    reponse = render(request, "notifications/liste.html", {
        "notifs": notifs, "nb_non_lues": len(non_lues)})
    if non_lues:
        Notification.objects.filter(pk__in=non_lues).update(lu=True)
    return reponse
