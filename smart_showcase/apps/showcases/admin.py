from django.contrib import admin
from django.utils.html import format_html
from .models import Showcase, ShowcaseSlot, SlotAssignment

class ShowcaseSlotInline(admin.TabularInline):
    model = ShowcaseSlot
    extra = 0
    readonly_fields = ('qr_token', 'get_public_url', 'get_current_card')
    fields = ('slot_number', 'visible_code', 'is_active', 'qr_token', 'get_public_url', 'get_current_card')

    @admin.display(description='URL Pública')
    def get_public_url(self, obj):
        if obj.pk:
            url = obj.get_public_url()
            return format_html('<a href="{}" target="_blank">Abrir QR</a>', url)
        return "-"

    @admin.display(description='Carta Actual')
    def get_current_card(self, obj):
        item = obj.current_item
        return str(item) if item else "Vacío"

@admin.register(Showcase)
class ShowcaseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'total_rows', 'total_columns', 'capacity', 'is_active')
    search_fields = ('code', 'name')
    list_filter = ('is_active',)
    inlines = [ShowcaseSlotInline]

@admin.register(ShowcaseSlot)
class ShowcaseSlotAdmin(admin.ModelAdmin):
    list_display = ('visible_code', 'showcase', 'slot_number', 'is_active', 'qr_token', 'get_card_info')
    search_fields = ('visible_code', 'showcase__code', 'qr_token')
    list_filter = ('showcase', 'is_active')
    readonly_fields = ('qr_token', 'get_qr_link')

    @admin.display(description='Carta Asignada')
    def get_card_info(self, obj):
        item = obj.current_item
        return str(item) if item else "Sin asignar"

    @admin.display(description='Enlace QR')
    def get_qr_link(self, obj):
        url = obj.get_public_url()
        return format_html('<a href="{}" target="_blank">{}</a>', url, url)

@admin.register(SlotAssignment)
class SlotAssignmentAdmin(admin.ModelAdmin):
    list_display = ('slot', 'item', 'is_active', 'assigned_at', 'unassigned_at', 'assigned_by')
    search_fields = ('slot__visible_code', 'item__sku', 'item__print__card__name')
    list_filter = ('is_active', 'assigned_at')
    readonly_fields = ('assigned_at',)
