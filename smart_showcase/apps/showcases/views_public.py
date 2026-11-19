from django.shortcuts import render, get_object_or_404
from apps.showcases.models import ShowcaseSlot
from apps.pricing.models import PriceQuote, PricingRuleConfig

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
            config = PricingRuleConfig.objects.filter(is_active=True).first()
            if not config:
                config = PricingRuleConfig.objects.create()
            
            # Cálculo provisional transparente basado en el costo del item
            base_cost = item.acquisition_cost
            margin_multiplier = 1 + (config.commercial_margin_percent / 100)
            provisional_cash = base_cost * margin_multiplier
            provisional_card = provisional_cash * (1 + (config.card_processing_fee_percent / 100))
            
            # Redondeo
            unit = config.rounding_unit or 100
            cash_price = round(float(provisional_cash) / unit) * unit
            card_price = round(float(provisional_card) / unit) * unit

    context = {
        'slot': slot,
        'item': item,
        'has_card': item is not None,
        'cash_price': cash_price,
        'card_price': card_price,
        'ref_usd': ref_usd,
        'quote_updated_at': quote_updated_at,
    }
    return render(request, 'showcases/public_slot_detail.html', context)
