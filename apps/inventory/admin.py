from django.contrib import admin
from .models import InventoryItem


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ("proprietaire", "item", "quantite", "est_relique",
                    "date_obtention")
    list_filter = ("est_relique",)