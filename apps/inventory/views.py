import os

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.economy.services import ErreurEconomie
from apps.shop.media_range import servir_media
from apps.shop.models import MEDIAS, Item
from . import services
from .forms import CadeauForm
from .models import Equipement, InventoryItem, ObjectTransfer

User = get_user_model()
SLOTS = {"cadre": "cadre", "decor": "decor"}


def _equipement(user):
    equip, _ = Equipement.objects.get_or_create(user=user)
    return equip


@login_required
def inventaire(request):
    objets = (InventoryItem.objects.filter(proprietaire=request.user)
              .select_related("item", "item__createur"))
    equip = Equipement.objects.filter(user=request.user).first()
    return render(request, "inventory/inventaire.html", {
        "objets": objets, "equip": equip})


@login_required
def telecharger(request, pk):
    item = get_object_or_404(Item, pk=pk)
    autorise = (
        request.user.est_divinite
        or item.createur_id == request.user.pk
        or InventoryItem.objects.filter(
            proprietaire=request.user, item=item).exists()
    )
    if not autorise:
        raise PermissionDenied
    # audio / vidéo : le téléchargement donne le fichier complet ;
    # avec ?voir=1 on affiche seulement la pochette ou la vignette.
    if item.categorie in MEDIAS and item.fichier and not request.GET.get("voir"):
        return servir_media(request, item.fichier, telecharger=True)
    fichier = item.image.storage.open(item.image.name, "rb")
    return FileResponse(fichier,
                        as_attachment=not request.GET.get("voir"),
                        filename=os.path.basename(item.image.name))


@login_required
@require_POST
def equiper(request, pk):
    item = get_object_or_404(Item, pk=pk)
    slot = SLOTS.get(item.categorie)
    if slot is None:
        messages.error(request, "Cet article ne s'équipe pas.")
        return redirect("inventaire")
    possede = InventoryItem.objects.filter(
        proprietaire=request.user, item=item).exists()
    if not possede:
        raise PermissionDenied
    equip = _equipement(request.user)
    setattr(equip, slot, item)
    equip.save()
    messages.success(request, "Équipé sur ton profil ✨")
    return redirect("inventaire")


@login_required
@require_POST
def retirer(request, slot):
    if slot not in SLOTS:
        return redirect("inventaire")
    equip = _equipement(request.user)
    setattr(equip, slot, None)
    equip.save()
    messages.success(request, "Retiré de ton profil.")
    return redirect("inventaire")


@login_required
@require_POST
def musique_profil(request, pk):
    item = get_object_or_404(Item, pk=pk, categorie="audio")
    if item.createur_id != request.user.pk:
        raise PermissionDenied
    if not item.est_actif or not item.extrait:
        messages.error(request, "Cet article n'est pas disponible.")
        return redirect("article", pk=pk)
    equip = _equipement(request.user)
    equip.musique = item
    equip.save()
    messages.success(request, "Cette musique est maintenant sur ton profil 🎵")
    return redirect("article", pk=pk)


@login_required
@require_POST
def musique_retirer(request):
    equip = _equipement(request.user)
    equip.musique = None
    equip.save()
    messages.success(request, "Musique retirée de ton profil.")
    return redirect("membre", pk=request.user.pk)


# ---------- Cadeaux d'objets ----------

@login_required
def offrir(request, pk):
    possession = get_object_or_404(
        InventoryItem.objects.select_related("item"),
        proprietaire=request.user, item_id=pk)
    membres = (User.objects.filter(is_active=True)
               .exclude(pk=request.user.pk).order_by("pseudo_whatsapp"))
    form = CadeauForm(request.POST or None, qs=membres)
    if request.method == "POST" and form.is_valid():
        try:
            services.offrir(request.user, form.cleaned_data["destinataire"].pk,
                            pk, form.cleaned_data["message"])
            messages.success(
                request, "Cadeau envoyé ! Il peut l'accepter ou le refuser 🎁")
            return redirect("cadeaux")
        except ErreurEconomie as e:
            form.add_error(None, str(e))
    return render(request, "inventory/offrir.html",
                  {"form": form, "item": possession.item})


@login_required
def cadeaux(request):
    services.traiter_echeances()
    u = request.user
    S = ObjectTransfer.Statut
    recus = (ObjectTransfer.objects.filter(destinataire=u, statut=S.ENVOYE)
             .select_related("expediteur", "item"))
    envoyes = (ObjectTransfer.objects.filter(expediteur=u, statut=S.ENVOYE)
               .select_related("destinataire", "item"))
    historique = (ObjectTransfer.objects
                  .filter(Q(expediteur=u) | Q(destinataire=u))
                  .exclude(statut=S.ENVOYE)
                  .select_related("expediteur", "destinataire", "item")[:20])
    return render(request, "inventory/cadeaux.html", {
        "recus": recus, "envoyes": envoyes, "historique": historique})


@login_required
@require_POST
def cadeau_action(request, pk):
    action = request.POST.get("action")
    try:
        if action == "accepter":
            services.accepter(request.user, pk)
            messages.success(request, "Cadeau accepté : il est dans ton "
                                      "inventaire 🎁")
        elif action == "refuser":
            services.refuser(request.user, pk)
            messages.success(request, "Cadeau refusé.")
        elif action == "annuler":
            services.annuler(request.user, pk)
            messages.success(request, "Cadeau annulé.")
        else:
            raise ErreurEconomie("Action inconnue.")
    except ErreurEconomie as e:
        messages.error(request, str(e))
    return redirect("cadeaux")
