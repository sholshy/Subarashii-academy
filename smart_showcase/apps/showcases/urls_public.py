from django.urls import path
from . import views_public

urlpatterns = [
    path('<uuid:qr_token>/', views_public.public_slot_detail_view, name='public_slot_detail'),
]
