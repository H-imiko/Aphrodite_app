import os

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse
from django.shortcuts import render, get_object_or_404

from apps.shop.models import Item
from .models import InventoryItem


@login_required
def inventaire(request):
    objets = (InventoryItem.objects.filter(proprietaire=request.user)
              .select_related("item", "item__createur"))
    return render(request, "inventory/inventaire.html", {"objets": objets})


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
    fichier = item.image.storage.open(item.image.name, "rb")
    return FileResponse(fichier,
                        as_attachment=not request.GET.get("voir"),
                        filename=os.path.basename(item.image.name))