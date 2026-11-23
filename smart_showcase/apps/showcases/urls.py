from django.urls import path
from . import views

urlpatterns = [
    path('', views.showcase_list_view, name='showcase_list'),
    path('intake/', views.showcase_quick_intake_view, name='showcase_quick_intake'),
    path('create/', views.showcase_create_view, name='showcase_create'),
    path('<int:showcase_id>/', views.showcase_grid_view, name='showcase_grid'),
    path('<int:showcase_id>/edit/', views.showcase_edit_view, name='showcase_edit'),
    path('<int:showcase_id>/delete/', views.showcase_delete_view, name='showcase_delete'),
    path('<int:showcase_id>/sheet/', views.download_showcase_sheet_view, name='download_showcase_sheet'),
    path('slot/<int:slot_id>/assign/', views.slot_assign_view, name='slot_assign'),
    path('slot/<int:slot_id>/unassign/', views.slot_unassign_view, name='slot_unassign'),
    path('slot/<int:slot_id>/qr/', views.download_slot_qr_view, name='download_slot_qr'),
]
