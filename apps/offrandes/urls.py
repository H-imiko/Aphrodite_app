from django.urls import path
from . import views

urlpatterns = [
    path("offrandes/envoyer/<int:pk>/", views.envoyer,
         name="offrande_envoyer"),
    path("offrandes/recues/<int:pk>/", views.recues, name="offrandes_recues"),
    path("offrandes/<int:pk>/masquer/", views.masquer, name="offrande_masquer"),
    path("offrandes/<int:pk>/bloquer/", views.bloquer, name="offrande_bloquer"),
    path("offrandes/blocages/", views.blocages, name="blocages"),
    path("offrandes/blocages/<int:pk>/debloquer/", views.debloquer,
         name="debloquer"),
    path("divinites/offrandes/", views.admin_catalogue,
         name="offrandes_admin"),
    path("divinites/offrandes/<int:pk>/", views.admin_modifier,
         name="offrande_admin_modifier"),
    path("divinites/offrandes/<int:pk>/basculer/", views.admin_basculer,
         name="offrande_admin_basculer"),
]
