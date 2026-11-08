from django.urls import path
from . import views

urlpatterns = [
    path("inventaire/", views.inventaire, name="inventaire"),
    path("inventaire/<int:pk>/telecharger/", views.telecharger,
         name="telecharger"),
    path("inventaire/<int:pk>/equiper/", views.equiper, name="equiper"),
    path("inventaire/<int:pk>/offrir/", views.offrir, name="offrir"),
    path("inventaire/retirer/<str:slot>/", views.retirer,
         name="retirer_equipement"),
    path("inventaire/musique/<int:pk>/", views.musique_profil,
         name="musique_profil"),
    path("inventaire/musique/retirer/", views.musique_retirer,
         name="musique_retirer"),
    path("cadeaux/", views.cadeaux, name="cadeaux"),
    path("cadeaux/<int:pk>/action/", views.cadeau_action,
         name="cadeau_action"),
]
