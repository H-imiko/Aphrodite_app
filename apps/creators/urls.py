from django.urls import path
from . import views

urlpatterns = [
    path("createur/postuler/", views.postuler, name="postuler"),
    path("divinites/candidatures/", views.candidatures, name="candidatures"),
    path("divinites/candidatures/<int:pk>/", views.candidature,
         name="candidature"),
    path("divinites/candidatures/<int:pk>/valider/",
         views.candidature_valider, name="candidature_valider"),
    path("divinites/candidatures/<int:pk>/refuser/",
         views.candidature_refuser, name="candidature_refuser"),
    path("candidatures/exemples/<int:pk>/", views.exemple_image,
         name="exemple_image"),
]