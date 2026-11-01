from django.urls import path
from . import views

urlpatterns = [
    path("boutique/", views.boutique, name="boutique"),
    path("boutique/<int:pk>/", views.article, name="article"),
    path("boutique/<int:pk>/acheter/", views.acheter, name="acheter"),
    path("mes-articles/", views.mes_articles, name="mes_articles"),
    path("mes-articles/nouveau/", views.nouvel_article, name="nouvel_article"),
    path("mes-articles/<int:pk>/basculer/", views.basculer_article,
         name="basculer_article"),
]