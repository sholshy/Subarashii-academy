from django.urls import path
from . import views

urlpatterns = [
    path('', views.pricing_dashboard_view, name='pricing_dashboard'),
    path('quote/<int:print_id>/', views.pricing_quote_create_view, name='pricing_quote_create'),
]
