from django.contrib import admin
from .models import AuditLog, Report, Sanction


class LectureSeule(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditLog)
class AuditLogAdmin(LectureSeule):
    list_display = ("date", "action", "auteur", "cible", "details")
    list_filter = ("action",)


@admin.register(Report)
class ReportAdmin(LectureSeule):
    list_display = ("date", "motif", "statut", "auteur", "traite_par")
    list_filter = ("statut", "motif")


@admin.register(Sanction)
class SanctionAdmin(LectureSeule):
    list_display = ("date", "type", "user", "par", "raison")
    list_filter = ("type",)
