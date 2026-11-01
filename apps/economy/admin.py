from django.contrib import admin
from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("date", "type", "expediteur", "destinataire",
                    "montant", "auteur")
    list_filter = ("type",)
    search_fields = ("destinataire__pseudo_whatsapp",
                     "expediteur__pseudo_whatsapp")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False