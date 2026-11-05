from django.urls import path
from . import views

urlpatterns = [
    path("commandes/", views.liste, name="commandes"),
    path("commandes/nouvelle/<int:vendeur_id>/", views.nouvelle,
         name="commande_nouvelle"),
    path("commandes/<int:pk>/", views.detail, name="commande"),
    path("commandes/<int:pk>/action/", views.action, name="commande_action"),
    path("commandes/<int:pk>/message/", views.message, name="commande_message"),
    path("commandes/<int:pk>/trancher/", views.trancher, name="commande_trancher"),
    path("divinites/litiges/", views.litiges, name="litiges"),
]
