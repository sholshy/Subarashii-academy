from django.urls import path
from . import views_public

urlpatterns = [
    path('', views_public.public_showcase_index_view, name='public_showcase_index'),
    path('<uuid:qr_token>/', views_public.public_slot_detail_view, name='public_slot_detail'),
]
