"""
URL Configuration for Subarashii Smart Showcase.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', RedirectView.as_view(url='/admin/login/', permanent=False, query_string=True)),
    # Módulos principales
    path('catalog/', include('apps.catalog.urls')),
    path('inventory/', include('apps.inventory.urls')),
    path('showcases/', include('apps.showcases.urls')),
    path('pricing/', include('apps.pricing.urls')),
    # Public showcase QR routing: /v/<qr_token>
    path('v/', include('apps.showcases.urls_public')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
