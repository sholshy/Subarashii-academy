from django.contrib import admin
from django.utils.html import format_html
from .models import InventoryItem, InventoryMovement

class InventoryMovementInline(admin.TabularInline):
    model = InventoryMovement
    extra = 0
    readonly_fields = ('from_status', 'to_status', 'from_location', 'to_location', 'user', 'reason', 'created_at')
    can_delete = False

@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('sku', 'get_thumbnail', 'get_card_name', 'get_print_code', 'condition', 'acquisition_cost', 'get_status_badge', 'location', 'acquisition_date')
    search_fields = ('sku', 'print__card__name', 'print__print_code', 'location')
    list_filter = ('status', 'condition', 'acquisition_date')
    inlines = [InventoryMovementInline]

    @admin.display(description='Carta')
    def get_card_name(self, obj):
        return obj.print.card.name

    @admin.display(description='Impresión')
    def get_print_code(self, obj):
        return f"{obj.print.print_code} ({obj.print.rarity})"

    @admin.display(description='Img')
    def get_thumbnail(self, obj):
        url = obj.print.image_url or (obj.print.image.url if obj.print.image else None)
        if url:
            return format_html('<img src="{}" style="height: 40px; border-radius: 3px;"/>', url)
        return "-"

    @admin.display(description='Estado')
    def get_status_badge(self, obj):
        color_map = {
            'IN_STOCK': '#10b981',      # Emerald
            'IN_SHOWCASE': '#f59e0b',   # Amber
            'RESERVED': '#3b82f6',      # Blue
            'SOLD': '#6b7280',          # Gray
            'RETURNED': '#8b5cf6',      # Purple
            'DAMAGED': '#ef4444',       # Red
            'LOST': '#b91c1c',          # Dark Red
        }
        color = color_map.get(obj.status, '#64748b')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-weight: bold; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display()
        )

    def get_readonly_fields(self, request, obj=None):
        # Vendedores no pueden alterar el costo de adquisición de un ítem ya creado
        if obj and hasattr(request.user, 'is_store_admin') and not request.user.is_store_admin:
            return ['acquisition_cost', 'sku', 'acquisition_date']
        return []

    def has_delete_permission(self, request, obj=None):
        if hasattr(request.user, 'is_store_admin'):
            return request.user.is_store_admin
        return request.user.is_superuser

@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = ('item', 'from_status', 'to_status', 'from_location', 'to_location', 'user', 'reason', 'created_at')
    search_fields = ('item__sku', 'reason')
    list_filter = ('to_status', 'created_at')
    readonly_fields = [f.name for f in InventoryMovement._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
