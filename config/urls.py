from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.accounts.urls')),
    path('', include('apps.economy.urls')),
    path('', include('apps.shop.urls')),
    path('', include('apps.inventory.urls')),
    path('', include('apps.creators.urls')),
    path('', include('apps.moderation.urls')),
    path('', include('apps.orders.urls')),
    path('', include('apps.notifications.urls')),
    path('', include('apps.social.urls')),
    path('', include('apps.offrandes.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)