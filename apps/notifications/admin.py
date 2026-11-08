from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("date", "user", "titre", "type", "lu")
    list_filter = ("type", "lu")
    search_fields = ("user__pseudo_whatsapp", "titre")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
