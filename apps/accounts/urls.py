from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("inscription/", views.inscription, name="inscription"),
    path("connexion/", views.ConnexionVue.as_view(), name="connexion"),
    path("deconnexion/", auth_views.LogoutView.as_view(),
         name="deconnexion"),
    path("profil/", views.profil, name="profil"),
    path("profil/modifier/", views.modifier_profil, name="modifier_profil"),
    path("parametres/", views.parametres, name="parametres"),
    path("parametres/supprimer/", views.supprimer_compte, name="supprimer_compte"),
    path("parametres/mot-de-passe/", views.changer_mot_de_passe,
         name="changer_mot_de_passe"),
    path("mot-de-passe-oublie/", views.mot_de_passe_oublie,
         name="mot_de_passe_oublie"),
    path("reglement/", views.reglement, name="reglement"),
    path("confidentialite/", views.confidentialite, name="confidentialite"),
    path("membre/<int:pk>/", views.membre, name="membre"),
    path("membre/<int:pk>/photo/<str:champ>/", views.photo_membre,
         name="photo_membre"),
]
