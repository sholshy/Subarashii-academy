from django.contrib import admin
from django.utils.html import format_html
from .models import Card, CardPrint

class CardPrintInline(admin.TabularInline):
    model = CardPrint
    extra = 1
    fields = ('get_thumbnail', 'print_code', 'set_name', 'rarity', 'edition', 'language', 'tcgplayer_product_id')
    readonly_fields = ('get_thumbnail',)

    @admin.display(description='Vista Previa')
    def get_thumbnail(self, obj):
        url = obj.image_url or (obj.image.url if obj.image else None)
        if url:
            return format_html('<img src="{}" style="height: 50px; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"/>', url)
        return "Sin Imagen"

@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ('name', 'ygoprodeck_id', 'card_type', 'race', 'attribute', 'atk', 'def_points', 'level', 'get_prints_count')
    search_fields = ('name', 'clean_name', 'ygoprodeck_id', 'archetype')
    list_filter = ('card_type', 'attribute', 'race')
    inlines = [CardPrintInline]

    @admin.display(description='Impresiones')
    def get_prints_count(self, obj):
        return obj.prints.count()

    def has_delete_permission(self, request, obj=None):
        # Solo administradores de la tienda pueden eliminar cartas del catálogo
        if hasattr(request.user, 'is_store_admin'):
            return request.user.is_store_admin
        return request.user.is_superuser

@admin.register(CardPrint)
class CardPrintAdmin(admin.ModelAdmin):
    list_display = ('get_thumbnail', 'get_card_name', 'print_code', 'set_name', 'rarity', 'edition', 'language', 'tcgplayer_product_id')
    search_fields = ('card__name', 'print_code', 'set_name', 'tcgplayer_product_id')
    list_filter = ('rarity', 'edition', 'language')

    @admin.display(description='Imagen')
    def get_thumbnail(self, obj):
        url = obj.image_url or (obj.image.url if obj.image else None)
        if url:
            return format_html('<img src="{}" style="height: 45px; border-radius: 4px;"/>', url)
        return "-"

    @admin.display(description='Carta')
    def get_card_name(self, obj):
        return obj.card.name

    def has_delete_permission(self, request, obj=None):
        if hasattr(request.user, 'is_store_admin'):
            return request.user.is_store_admin
        return request.user.is_superuser
