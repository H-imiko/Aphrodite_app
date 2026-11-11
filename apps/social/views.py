from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.economy.services import ErreurEconomie
from apps.shop.models import Item
from . import services
from .models import Abonnement, Like


@login_required
@require_POST
def abonner(request, pk):
    try:
        suivi = services.basculer_abonnement(request.user, pk)
        messages.success(request, "Tu es abonné ✨" if suivi
                         else "Abonnement retiré.")
    except ErreurEconomie as e:
        messages.error(request, str(e))
    return redirect("membre", pk=pk)


@login_required
@require_POST
def aimer(request, pk):
    try:
        services.basculer_like(request.user, pk)
    except ErreurEconomie as e:
        messages.error(request, str(e))
    # On revient la ou le membre a clique : aimer depuis une vignette ne doit
    # pas l'envoyer sur la fiche de l'article.
    suivant = request.POST.get("suivant", "")
    if suivant and url_has_allowed_host_and_scheme(
            suivant, allowed_hosts={request.get_host()},
            require_https=request.is_secure()):
        return redirect(suivant)
    return redirect("article", pk=pk)


@login_required
def fil(request):
    ids = Abonnement.objects.filter(
        abonne=request.user).values_list("createur_id", flat=True)
    articles = list(Item.objects.filter(est_actif=True,
                                        createur_id__in=list(ids))
                    .select_related("createur")
                    .order_by("-date_creation")[:48])
    aimes = set(Like.objects.filter(
        user=request.user, item_id__in=[a.pk for a in articles]
    ).values_list("item_id", flat=True))
    return render(request, "social/fil.html", {
        "articles": articles, "nb_suivis": len(list(ids)), "aimes": aimes})


@login_required
def favoris(request):
    likes = list(Like.objects.filter(user=request.user, item__est_actif=True)
                 .select_related("item", "item__createur")[:60])
    return render(request, "social/favoris.html", {
        "likes": likes, "aimes": {l.item_id for l in likes}})
