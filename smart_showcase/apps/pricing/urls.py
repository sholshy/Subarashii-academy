from django.urls import path
from . import views

urlpatterns = [
    path('', views.pricing_dashboard_view, name='pricing_dashboard'),
    path('quote/<int:print_id>/', views.pricing_quote_create_view, name='pricing_quote_create'),
    path('quote/<int:print_id>/sync-api/', views.pricing_sync_quote_api_view, name='pricing_sync_quote_api'),
    path('card/<int:card_id>/sync-all-api/', views.pricing_sync_card_prints_api_view, name='pricing_sync_card_prints_api'),
    path('api/quote-preview/', views.pricing_api_quote_preview_view, name='pricing_api_quote_preview'),
]
