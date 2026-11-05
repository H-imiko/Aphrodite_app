from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from apps.economy.services import ErreurEconomie
from apps.inventory.models import InventoryItem
from apps.moderation.models import AuditLog
from apps.moderation.services import journaliser
from .forms import ArticleForm
from .models import Item
from .services import acheter as acheter_article

PAR_PAGE = 12
TRIS = {
    "recent": ("Plus récents", ("-est_mis_en_avant", "-date_creation")),
    "populaires": ("Plus populaires", ("-nb_achats", "-date_creation")),
    "prix_asc": ("Prix croissant", ("prix_cubis", "-date_creation")),
    "prix_desc": ("Prix décroissant", ("-prix_cubis", "-date_creation")),
}


def _entier(valeur):
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return None


def _supprimer_fichier(fichier_champ, ancien_nom):
    """Efface un ancien fichier du disque (sans jamais faire planter la page)."""
    if not ancien_nom:
        return
    try:
        fichier_champ.storage.delete(ancien_nom)
    except Exception:
        pass


@login_required
def boutique(request):
    q = request.GET.get("q", "").strip()[:60]
    cat = request.GET.get("categorie", "")
    tri = request.GET.get("tri", "recent")
    if tri not in TRIS:
        tri = "recent"

    articles = (Item.objects.filter(est_actif=True)
                .select_related("createur")
                .annotate(nb_achats=Count("possessions")))
    if q:
        articles = articles.filter(
            Q(titre__icontains=q) | Q(description__icontains=q)
            | Q(createur__pseudo_whatsapp__icontains=q))
    if cat in Item.Categorie.values:
        articles = articles.filter(categorie=cat)
    else:
        cat = ""
    articles = articles.order_by(*TRIS[tri][1])

    page = Paginator(articles, PAR_PAGE).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    possedes = set(InventoryItem.objects.filter(
        proprietaire=request.user).values_list("item_id", flat=True))
    return render(request, "shop/boutique.html", {
        "page": page, "total": page.paginator.count,
        "q": q, "cat": cat, "tri": tri,
        "categories": Item.Categorie.choices,
        "tris": [(cle, nom) for cle, (nom, _) in TRIS.items()],
        "querystring": params.urlencode(),
        "possedes": possedes})


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
        "article": item, "acces": acces, "possede": possede,
        "est_proprietaire": est_proprietaire,
        "nb_achats": item.possessions.count() if est_proprietaire else 0})


@login_required
def acheter(request, pk):
    item = get_object_or_404(
        Item.objects.select_related("createur"), pk=pk, est_actif=True)
    if item.createur_id == request.user.pk:
        messages.error(request, "C'est ton propre article.")
        return redirect("article", pk=pk)
    if InventoryItem.objects.filter(
            proprietaire=request.user, item=item).exists():
        messages.info(request, "Tu possèdes déjà cet article.")
        return redirect("article", pk=pk)

    if request.method == "POST":
        prix = _entier(request.POST.get("prix"))
        if prix is None:
            messages.error(request, "Confirme l'achat depuis la page de l'article.")
            return redirect("article", pk=pk)
        try:
            acheter_article(request.user, pk, prix_attendu=prix)
            messages.success(
                request, "Achat réussi ! L'article est dans ton inventaire 🎁")
            return redirect("inventaire")
        except ErreurEconomie as e:
            messages.error(request, str(e))
            return redirect("acheter", pk=pk)

    solde = request.user.solde_cubis
    gratuit = request.user.est_divinite
    return render(request, "shop/acheter_confirmation.html", {
        "article": item, "solde_apres": solde - item.prix_cubis,
        "manque": max(item.prix_cubis - solde, 0),
        "peut_payer": gratuit or solde >= item.prix_cubis})


@login_required
def mes_articles(request):
    if not request.user.peut_publier:
        raise PermissionDenied
    articles = (Item.objects.filter(createur=request.user)
                .annotate(nb_achats=Count("possessions")))
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


def _article_a_moi(request, pk):
    if not request.user.peut_publier:
        raise PermissionDenied
    return get_object_or_404(Item, pk=pk, createur=request.user)


@login_required
def modifier_article(request, pk):
    item = _article_a_moi(request, pk)
    ancienne_image = item.image.name
    ancien_apercu = item.apercu.name
    form = ArticleForm(request.POST or None, request.FILES or None,
                       instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        if item.image.name != ancienne_image:
            _supprimer_fichier(item.image, ancienne_image)
            if item.apercu.name != ancien_apercu:
                _supprimer_fichier(item.apercu, ancien_apercu)
        messages.success(request, "Article modifié ✨")
        return redirect("article", pk=item.pk)
    return render(request, "shop/article_form.html",
                  {"form": form, "article": item})


@login_required
def supprimer_article(request, pk):
    item = _article_a_moi(request, pk)
    nb_achats = item.possessions.count()
    signale = item.signalements.exists()
    if request.method == "POST":
        if nb_achats or signale:
            messages.error(
                request, "Cet article ne peut pas être supprimé. Masque-le.")
            return redirect("mes_articles")
        image, apercu = item.image, item.apercu
        nom_image, nom_apercu = image.name, apercu.name
        item.delete()
        _supprimer_fichier(image, nom_image)
        _supprimer_fichier(apercu, nom_apercu)
        messages.success(request, "Article supprimé.")
        return redirect("mes_articles")
    return render(request, "shop/article_supprimer.html", {
        "article": item, "nb_achats": nb_achats, "signale": signale})


@login_required
@require_POST
def basculer_article(request, pk):
    item = get_object_or_404(Item, pk=pk)
    proprietaire = item.createur_id == request.user.pk
    if not proprietaire and not request.user.est_divinite:
        raise PermissionDenied
    if proprietaire:
        if not request.user.peut_publier:
            raise PermissionDenied
        if not item.est_actif and item.masque_moderation:
            messages.error(
                request,
                "Cet article a été masqué par la modération. "
                "Contacte une Divinité.")
            return redirect("mes_articles")

    item.est_actif = not item.est_actif
    if proprietaire:
        item.save(update_fields=["est_actif"])
    else:
        item.masque_moderation = not item.est_actif
        item.save(update_fields=["est_actif", "masque_moderation"])
        journaliser(
            request.user,
            AuditLog.Action.ARTICLE_AFFICHE if item.est_actif
            else AuditLog.Action.ARTICLE_MASQUE,
            item.createur, item.titre)
    messages.success(request, "Article affiché." if item.est_actif
                     else "Article masqué.")
    if proprietaire:
        return redirect("mes_articles")
    return redirect("article", pk=item.pk)
