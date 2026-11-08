from django.contrib import admin
from .models import Abonnement, Like


@admin.register(Abonnement)
class AbonnementAdmin(admin.ModelAdmin):
    list_display = ("date", "abonne", "createur")


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ("date", "user", "item")
