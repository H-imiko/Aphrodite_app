from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from apps.economy.services import ErreurEconomie
from apps.inventory.models import InventoryItem
from .forms import ArticleForm
from .models import Item
from .services import acheter as acheter_article
from apps.moderation.models import AuditLog
from apps.moderation.services import journaliser


@login_required
def boutique(request):
    articles = Item.objects.filter(est_actif=True).select_related("createur")
    cat = request.GET.get("categorie")
    if cat in Item.Categorie.values:
        articles = articles.filter(categorie=cat)
    return render(request, "shop/boutique.html", {
        "articles": articles, "categories": Item.Categorie.choices})


@login_required
def article(request, pk):
    item = get_object_or_404(Item.objects.select_related("createur"), pk=pk)
    est_proprietaire = item.createur_id == request.user.pk
    if not item.est_actif and not (est_proprietaire or request.user.est_divinite):
        raise Http404
    possede = InventoryItem.objects.filter(
        proprietaire=request.user, item=item).exists()
    acces = possede or est_proprietaire or request.user.est_divinite
    return render(request, "shop/article.html", {
        "article": item, "acces": acces})


@login_required
@require_POST
def acheter(request, pk):
    try:
        acheter_article(request.user, pk)
        messages.success(request, "Achat réussi ! L'article est dans ton inventaire 🎁")
        return redirect("inventaire")
    except ErreurEconomie as e:
        messages.error(request, str(e))
        return redirect("article", pk=pk)


@login_required
def mes_articles(request):
    if not request.user.peut_publier:
        raise PermissionDenied
    articles = Item.objects.filter(createur=request.user)
    return render(request, "shop/mes_articles.html", {"articles": articles})


@login_required
def nouvel_article(request):
    if not request.user.peut_publier:
        raise PermissionDenied
    form = ArticleForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        art = form.save(commit=False)
        art.createur = request.user
        art.est_officiel = request.user.est_divinite
        art.save()
        messages.success(request, "Article publié ✨")
        return redirect("mes_articles")
    return render(request, "shop/article_form.html", {"form": form})


@login_required
@require_POST

def basculer_article(request, pk):
    item = get_object_or_404(Item, pk=pk)
    par_divinite = item.createur_id != request.user.pk
    if par_divinite and not request.user.est_divinite:
        raise PermissionDenied
    item.est_actif = not item.est_actif
    item.save(update_fields=["est_actif"])
    if par_divinite:
        journaliser(
            request.user,
            AuditLog.Action.ARTICLE_AFFICHE if item.est_actif
            else AuditLog.Action.ARTICLE_MASQUE,
            item.createur, item.titre)
    messages.success(request, "Article affiché." if item.est_actif
                     else "Article masqué.")
    if par_divinite:
        return redirect("article", pk=item.pk)
    return redirect("mes_articles")