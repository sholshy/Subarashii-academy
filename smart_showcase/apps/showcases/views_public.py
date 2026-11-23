import re
from urllib.parse import quote_plus
from django.shortcuts import render, get_object_or_404, redirect
from apps.showcases.models import ShowcaseSlot
from apps.pricing.models import PriceQuote, PricingRuleConfig

def public_showcase_index_view(request):
    """Si se accede a /v/ directamente sin token, redirige a la lista de vitrinas."""
    return redirect('showcase_list')

def public_slot_detail_view(request, qr_token):
    """
    Página pública responsive optimizada para dispositivos móviles al escanear el QR.
    No requiere inicio de sesión.
    Nunca expone datos administrativos confidenciales (costos de adquisición, notas internas, márgenes).
    """
    slot = get_object_or_404(
        ShowcaseSlot.objects.select_related('showcase'),
        qr_token=qr_token,
        is_active=True
    )
    
    assignment = slot.current_assignment
    item = assignment.item if assignment else None
    
    # Obtener cotización de precios si existe
    price_quote = None
    cash_price = None
    card_price = None
    ref_usd = None
    quote_updated_at = None

    if item:
        price_quote = PriceQuote.objects.filter(
            card_print=item.print,
            is_current=True
        ).order_by('-created_at').first()

        if price_quote:
            cash_price = price_quote.calculated_cash_price
            card_price = price_quote.calculated_card_price
            ref_usd = price_quote.reference_price_usd
            quote_updated_at = price_quote.created_at
        else:
            # Si no hay cotización previa, calcular un precio de referencia base
            from apps.pricing.services import PricingService
            config = PricingService.get_active_config()
            cash_price, card_price = PricingService.calculate_prices_from_clp_cost(item.acquisition_cost, config)

    # Determinar número de WhatsApp configurado (vitrina específica o configuración de tienda)
    active_config = PricingRuleConfig.objects.filter(is_active=True).first()
    raw_whatsapp = slot.showcase.contact_whatsapp or (active_config.store_whatsapp_number if active_config else '') or '+56912345678'
    whatsapp_phone = re.sub(r'[^\d]', '', raw_whatsapp)

    # Construir enlace directo a WhatsApp con mensaje personalizado
    if item:
        price_text = f" - ${cash_price:,.0f} CLP".replace(',', '.') if cash_price else ""
        msg = f"Hola Subarashii! Quiero consultar/reservar la carta {item.print.card.name} ({item.print.print_code} - {item.get_condition_display()}) exhibida en el espacio {slot.visible_code}{price_text}"
    else:
        msg = f"Hola Subarashii! Vi el espacio {slot.visible_code} en la vitrina {slot.showcase.name} y me gustaría consultar disponibilidad de cartas."

    whatsapp_url = f"https://wa.me/{whatsapp_phone}?text={quote_plus(msg)}"

    # Verificar si el usuario que consulta tiene permisos de administración/vendedor
    is_admin = False
    if request.user.is_authenticated:
        is_admin = getattr(request.user, 'is_store_seller', False) or request.user.is_staff or request.user.is_superuser

    context = {
        'slot': slot,
        'item': item,
        'has_card': item is not None,
        'cash_price': cash_price,
        'card_price': card_price,
        'ref_usd': ref_usd,
        'quote_updated_at': quote_updated_at,
        'whatsapp_phone': whatsapp_phone,
        'whatsapp_url': whatsapp_url,
        'is_admin': is_admin,
    }
    return render(request, 'showcases/public_slot_detail.html', context)
