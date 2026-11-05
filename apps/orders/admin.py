from django.contrib import admin
from .models import Order


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("pk", "titre", "acheteur", "vendeur", "prix_cubis",
                    "statut", "date_creation")
    list_filter = ("statut",)
    search_fields = ("titre", "acheteur__pseudo_whatsapp",
                     "vendeur__pseudo_whatsapp")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
