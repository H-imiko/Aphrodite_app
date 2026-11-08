from django.contrib import admin
from .models import Equipement, InventoryItem, ObjectTransfer


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ("proprietaire", "item", "quantite", "est_relique",
                    "date_obtention")
    list_filter = ("est_relique",)


@admin.register(Equipement)
class EquipementAdmin(admin.ModelAdmin):
    list_display = ("user", "cadre", "decor", "musique")


@admin.register(ObjectTransfer)
class ObjectTransferAdmin(admin.ModelAdmin):
    list_display = ("date", "item", "expediteur", "destinataire", "statut")
    list_filter = ("statut",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
