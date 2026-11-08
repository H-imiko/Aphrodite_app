from django.contrib import admin
from .models import Blocage, Offrande, OffrandeEnvoyee


@admin.register(Offrande)
class OffrandeAdmin(admin.ModelAdmin):
    list_display = ("nom", "prix_cubis", "est_actif", "ordre")


@admin.register(OffrandeEnvoyee)
class OffrandeEnvoyeeAdmin(admin.ModelAdmin):
    list_display = ("date", "offrande", "expediteur", "destinataire",
                    "anonyme", "masque")
    list_filter = ("anonyme", "masque")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Blocage)
class BlocageAdmin(admin.ModelAdmin):
    list_display = ("date", "bloqueur", "bloque", "via_anonyme")
