from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import TemplateView

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
    path("parametres/langue/", views.changer_langue, name="changer_langue"),
    path("parametres/supprimer/", views.supprimer_compte, name="supprimer_compte"),
    path("parametres/mot-de-passe/", views.changer_mot_de_passe,
         name="changer_mot_de_passe"),
    path("mot-de-passe-oublie/", views.MotDePasseOublieVue.as_view(),
         name="mot_de_passe_oublie"),
    path("mot-de-passe-oublie/envoye/",
         TemplateView.as_view(
             template_name="accounts/mot_de_passe_envoye.html"),
         name="mot_de_passe_envoye"),
    path("mot-de-passe-oublie/sans-email/", views.demande_acces,
         name="mot_de_passe_sans_email"),
    path("reinitialiser/<uidb64>/<token>/",
         views.ReinitialiserMotDePasseVue.as_view(),
         name="reinitialiser_mot_de_passe"),
    path("reglement/", views.reglement, name="reglement"),
    path("confidentialite/", views.confidentialite, name="confidentialite"),
    path("membre/<int:pk>/", views.membre, name="membre"),
    path("membre/<int:pk>/photo/<str:champ>/", views.photo_membre,
         name="photo_membre"),
]
