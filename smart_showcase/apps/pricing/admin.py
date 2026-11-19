from django.contrib import admin
from .models import PricingRuleConfig, PriceQuote

@admin.register(PricingRuleConfig)
class PricingRuleConfigAdmin(admin.ModelAdmin):
    list_display = ('name', 'usd_to_clp_rate', 'commercial_margin_percent', 'cash_discount_percent', 'is_active', 'updated_at')

@admin.register(PriceQuote)
class PriceQuoteAdmin(admin.ModelAdmin):
    list_display = ('card_print', 'source', 'reference_price_usd', 'calculated_cash_price', 'calculated_card_price', 'is_current', 'created_at')
    list_filter = ('source', 'is_current', 'created_at')
    search_fields = ('card_print__print_code', 'card_print__card__name')
