from django.contrib import admin
from .models import Item


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("titre", "createur", "prix_cubis", "categorie",
                    "est_officiel", "est_mis_en_avant", "est_actif")
    list_filter = ("categorie", "est_officiel", "est_mis_en_avant", "est_actif")
    search_fields = ("titre", "createur__pseudo_whatsapp")