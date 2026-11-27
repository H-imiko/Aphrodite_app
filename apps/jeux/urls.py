from django.urls import path

from . import views

urlpatterns = [
    path("jeux/", views.hall, name="jeux"),
    path("jeux/demineur/", views.demineur, name="demineur"),
    path("jeux/<slug:jeu>/", views.jeu, name="jeu"),
]
