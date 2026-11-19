from django.urls import path
from . import views

urlpatterns = [
    path('', views.inventory_list_view, name='inventory_list'),
    path('create/', views.inventory_create_view, name='inventory_create'),
    path('<int:item_id>/', views.inventory_detail_view, name='inventory_detail'),
    path('<int:item_id>/status/', views.inventory_update_status_view, name='inventory_update_status'),
]
