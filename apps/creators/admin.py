from django.contrib import admin
from .models import Candidature


@admin.register(Candidature)
class CandidatureAdmin(admin.ModelAdmin):
    list_display = ("user", "statut", "date_creation", "traitee_par")
    list_filter = ("statut",)
    readonly_fields = ("user", "types_creation", "message", "statut",
                       "motif_refus", "traitee_par", "date_creation",
                       "date_traitement")

    def has_add_permission(self, request):
        return False