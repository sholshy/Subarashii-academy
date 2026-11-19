from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from apps.catalog.models import Card, CardPrint
from apps.pricing.models import PricingRuleConfig, PriceQuote
from apps.pricing.services import PricingService, parse_decimal_input
from apps.pricing.exchange_service import ExchangeRateService
from apps.pricing.card_price_service import CardPriceAPIService

@login_required
def pricing_dashboard_view(request):
    """Panel de configuración de precios, tasa USD y cotizaciones históricas."""
    config = PricingService.get_active_config()

    if request.method == 'POST' and 'sync_usd_rate' in request.POST:
        auto_recalc = request.POST.get('auto_recalc') == '1'
        new_rate, recalc_count = ExchangeRateService.update_config_rate(auto_recalculate=auto_recalc)
        if new_rate:
            msg = f"Tipo de cambio actualizado exitosamente vía API: $1 USD = ${new_rate} CLP."
            if auto_recalc and recalc_count > 0:
                msg += f" Se recalcularon {recalc_count} cotizaciones activas."
            messages.success(request, msg)
        else:
            messages.error(request, "No fue posible conectar con las APIs de tipo de cambio en este momento.")
        return redirect('pricing_dashboard')

    if request.method == 'POST' and 'update_config' in request.POST:
        config.store_whatsapp_number = request.POST.get('store_whatsapp_number', '+56912345678').strip()
        config.usd_to_clp_rate = parse_decimal_input(request.POST.get('usd_to_clp_rate'), default=Decimal('950.00'))
        config.commercial_margin_percent = parse_decimal_input(request.POST.get('commercial_margin_percent'), default=Decimal('25.00'))
        config.cash_discount_percent = parse_decimal_input(request.POST.get('cash_discount_percent'), default=Decimal('5.00'))
        config.card_processing_fee_percent = parse_decimal_input(request.POST.get('card_processing_fee_percent'), default=Decimal('2.95'))
        try:
            config.rounding_unit = int(request.POST.get('rounding_unit', '100'))
        except (ValueError, TypeError):
            config.rounding_unit = 100
        config.save()

        messages.success(request, "Configuración general de precios y WhatsApp guardada exitosamente.")
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

            ref_usd = parse_decimal_input(usd_val, default=Decimal('0.00'))
            quote = PricingService.save_quote(
                card_print=card_print,
                reference_price_usd=ref_usd,
                source=PriceQuote.Source.MANUAL
            )
            messages.success(request, f"Cotización generada: Efectivo ${quote.calculated_cash_price:,.0f} | Tarjeta ${quote.calculated_card_price:,.0f}")
        else:
            cash = parse_decimal_input(request.POST.get('custom_cash_price'), default=Decimal('0'))
            card = parse_decimal_input(request.POST.get('custom_card_price'), default=Decimal('0'))
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

@login_required
def pricing_sync_quote_api_view(request, print_id):
    """Obtiene automáticamente el precio USD desde TCGplayer/YGOPRODeck y genera la cotización."""
    card_print = get_object_or_404(CardPrint.objects.select_related('card'), id=print_id)
    quote = CardPriceAPIService.sync_quote_for_print(card_print)

    if quote:
        messages.success(
            request,
            f"Cotización sincronizada vía API para {card_print.print_code}: "
            f"${quote.reference_price_usd} USD -> Efectivo ${quote.calculated_cash_price:,.0f} | Tarjeta ${quote.calculated_card_price:,.0f}"
        )
    else:
        messages.error(
            request,
            f"No se encontró precio de referencia en la API para la impresión {card_print.print_code}."
        )

    return redirect('catalog_card_detail', card_id=card_print.card_id)

@login_required
def pricing_sync_card_prints_api_view(request, card_id):
    """Sincroniza y cotiza todas las impresiones de una carta en un solo clic vía API."""
    card = get_object_or_404(Card, id=card_id)
    synced_count = CardPriceAPIService.sync_all_prints_for_card(card)

    if synced_count > 0:
        messages.success(request, f"Se cotizaron exitosamente {synced_count} impresiones de '{card.name}' vía API.")
    else:
        messages.warning(request, f"No se pudieron obtener precios en dólares para las impresiones de '{card.name}'.")

    return redirect('catalog_card_detail', card_id=card.id)

