from django.urls import path
from . import views

urlpatterns = [
    path("portefeuille/", views.portefeuille, name="portefeuille"),
    path("transactions/", views.transactions, name="transactions"),
    path("tresor/", views.tresor, name="tresor"),
]