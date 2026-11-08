from django.urls import path
from . import views

urlpatterns = [
    path("abonner/<int:pk>/", views.abonner, name="abonner"),
    path("aimer/<int:pk>/", views.aimer, name="aimer"),
    path("fil/", views.fil, name="fil"),
    path("favoris/", views.favoris, name="favoris"),
]
