from django.urls import path
from . import views

urlpatterns = [
    path("divinites/", views.panel, name="panel"),
    path("divinites/economie/", views.economie, name="economie"),
    path("divinites/journal/", views.journal, name="journal"),
]