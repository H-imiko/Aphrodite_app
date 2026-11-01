from django.urls import path
from . import views

urlpatterns = [
    path("inventaire/", views.inventaire, name="inventaire"),
    path("inventaire/<int:pk>/telecharger/", views.telecharger, name="telecharger"),
]