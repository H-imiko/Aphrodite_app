from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("email",)
    list_display = ("pseudo_whatsapp", "email", "espece", "type_compte",
                    "createur_valide", "est_divinite", "est_suspendu")
    list_filter = ("espece", "type_compte", "createur_valide",
                   "est_divinite", "est_suspendu")
    search_fields = ("email", "pseudo_whatsapp")
    readonly_fields = ("solde_cubis", "serie_connexion",
                       "derniere_connexion_bonus")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profil RP", {"fields": ("pseudo_whatsapp", "titre", "espece",
                                  "type_compte", "bio_rp", "numero_whatsapp",
                                  "avatar", "banniere", "date_naissance")}),
        ("Rôles et modération", {"fields": ("est_divinite", "createur_valide",
                                            "est_suspendu",
                                            "date_fin_suspension")}),
        ("Cubis", {"fields": ("solde_cubis", "serie_connexion",
                              "derniere_connexion_bonus")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser",
                                    "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",),
                "fields": ("email", "pseudo_whatsapp", "password1",
                           "password2")}),
    )