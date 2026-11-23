from django.urls import path
from . import views

urlpatterns = [
    path('', views.catalog_list_view, name='catalog_list'),
    path('card/<int:card_id>/', views.catalog_card_detail_view, name='catalog_card_detail'),
    path('create/', views.catalog_card_create_view, name='catalog_card_create'),
    path('remote-search/', views.catalog_remote_search_view, name='catalog_remote_search'),
    path('import/<int:ygoprodeck_id>/', views.catalog_import_card_view, name='catalog_import_card'),
    path('api/search/', views.catalog_api_search_view, name='catalog_api_search'),
    path('api/card-details/<int:ygoprodeck_id>/', views.catalog_api_card_details_view, name='catalog_api_card_details'),
]
