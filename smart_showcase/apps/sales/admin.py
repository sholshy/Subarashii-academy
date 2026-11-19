from django.contrib import admin
from .models import Order, OrderItem, InventoryReservation

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('item', 'unit_price')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'status', 'payment_type', 'total_amount', 'customer_name', 'created_at')
    list_filter = ('status', 'payment_type', 'created_at')
    search_fields = ('order_number', 'customer_name', 'customer_email')
    inlines = [OrderItemInline]

@admin.register(InventoryReservation)
class InventoryReservationAdmin(admin.ModelAdmin):
    list_display = ('item', 'order', 'expires_at', 'is_active', 'created_at')
    list_filter = ('is_active', 'expires_at')
