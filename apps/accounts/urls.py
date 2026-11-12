from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("inscription/", views.inscription, name="inscription"),
    path("connexion/", auth_views.LoginView.as_view(
        template_name="accounts/connexion.html",
        redirect_authenticated_user=True), name="connexion"),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="deconnexion"),
    path("profil/", views.profil, name="profil"),
    path("profil/modifier/", views.modifier_profil, name="modifier_profil"),
    path("parametres/", views.parametres, name="parametres"),
    path("parametres/supprimer/", views.supprimer_compte, name="supprimer_compte"),
    path("reglement/", views.reglement, name="reglement"),
    path("membre/<int:pk>/", views.membre, name="membre"),
]