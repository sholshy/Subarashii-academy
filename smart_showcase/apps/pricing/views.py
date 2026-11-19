from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from apps.catalog.models import CardPrint
from apps.pricing.models import PricingRuleConfig, PriceQuote
from apps.pricing.services import PricingService

@login_required
def pricing_dashboard_view(request):
    """Panel de configuración de precios y cotizaciones históricas."""
    config = PricingService.get_active_config()

    if request.method == 'POST' and 'update_config' in request.POST:
        config.usd_to_clp_rate = Decimal(request.POST.get('usd_to_clp_rate', '950.00'))
        config.commercial_margin_percent = Decimal(request.POST.get('commercial_margin_percent', '25.00'))
        config.cash_discount_percent = Decimal(request.POST.get('cash_discount_percent', '5.00'))
        config.card_processing_fee_percent = Decimal(request.POST.get('card_processing_fee_percent', '2.95'))
        config.rounding_unit = int(request.POST.get('rounding_unit', '100'))
        config.save()

        messages.success(request, "Configuración general de precios actualizada.")
        return redirect('pricing_dashboard')

    if request.method == 'POST' and 'recalculate_quotes' in request.POST:
        recalc_count = PricingService.recalculate_all_quotes(config)
        messages.success(request, f"Se recalcularon {recalc_count} cotizaciones vigentes con la nueva tasa.")
        return redirect('pricing_dashboard')

    quotes = PriceQuote.objects.filter(is_current=True).select_related('card_print__card').order_by('-created_at')[:50]

    context = {
        'config': config,
        'quotes': quotes,
        'total_quotes_count': PriceQuote.objects.filter(is_current=True).count()
    }
    return render(request, 'pricing/dashboard.html', context)

@login_required
def pricing_quote_create_view(request, print_id):
    """Fijación manual o en USD de precio para una impresión específica."""
    card_print = get_object_or_404(CardPrint.objects.select_related('card'), id=print_id)

    if request.method == 'POST':
        mode = request.POST.get('mode', 'usd')

        if mode == 'usd':
            usd_val = request.POST.get('reference_price_usd', '').strip()
            if not usd_val:
                messages.error(request, "Debes ingresar un valor en USD.")
                return redirect('pricing_quote_create', print_id=card_print.id)

            ref_usd = Decimal(usd_val)
            quote = PricingService.save_quote(
                card_print=card_print,
                reference_price_usd=ref_usd,
                source=PriceQuote.Source.MANUAL
            )
            messages.success(request, f"Cotización generada: Efectivo ${quote.calculated_cash_price:,.0f} | Tarjeta ${quote.calculated_card_price:,.0f}")
        else:
            cash = Decimal(request.POST.get('custom_cash_price', '0'))
            card = Decimal(request.POST.get('custom_card_price', '0'))
            quote = PricingService.save_quote(
                card_print=card_print,
                source=PriceQuote.Source.MANUAL,
                custom_cash_price=cash,
                custom_card_price=card
            )
            messages.success(request, f"Precios manuales fijados: Efectivo ${quote.calculated_cash_price:,.0f} | Tarjeta ${quote.calculated_card_price:,.0f}")

        return redirect('catalog_card_detail', card_id=card_print.card_id)

    current_quote = PriceQuote.objects.filter(card_print=card_print, is_current=True).first()
    config = PricingService.get_active_config()

    return render(request, 'pricing/quote_create.html', {
        'card_print': card_print,
        'current_quote': current_quote,
        'config': config
    })
