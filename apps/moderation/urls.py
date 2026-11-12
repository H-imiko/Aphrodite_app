from django.urls import path
from . import views, views_public

urlpatterns = [
    path("signaler/<str:type_cible>/<int:pk>/", views_public.signaler,
         name="signaler"),
    path("suspendu/", views_public.suspendu, name="suspendu"),
    path("divinites/", views.panel, name="panel"),
    path("divinites/economie/", views.economie, name="economie"),
    path("divinites/journal/", views.journal, name="journal"),
    path("divinites/equipe/", views.equipe, name="equipe"),
    path("divinites/equipe/<int:pk>/role/", views.equipe_action,
         name="equipe_action"),
    path("divinites/signalements/", views.signalements, name="signalements"),
    path("divinites/signalements/<int:pk>/", views.signalement,
         name="signalement"),
    path("divinites/signalements/<int:pk>/action/", views.signalement_action,
         name="signalement_action"),
    path("divinites/membres/<int:pk>/", views.membre_moderation,
         name="membre_moderation"),
    path("divinites/membres/<int:pk>/sanction/", views.sanction_action,
         name="sanction_action"),
]
