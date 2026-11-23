from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.conf import settings
from django.db import transaction
from django.utils.text import slugify
from apps.catalog.models import Card, CardPrint
from apps.inventory.models import InventoryItem
from apps.pricing.models import PriceQuote, PricingRuleConfig
from apps.pricing.services import PricingService, parse_decimal_input
from apps.showcases.models import Showcase, ShowcaseSlot, SlotAssignment
from apps.showcases.services import ShowcaseService
from apps.showcases.qr_generator import QRGeneratorService

def _get_request_user(request):
    """Retorna el usuario actual, o en modo local (DEBUG) el usuario admin para facilitar la gestión."""
    if request.user.is_authenticated:
        return request.user
    if getattr(settings, 'DEBUG', False):
        from apps.accounts.models import CustomUser
        return CustomUser.objects.filter(is_superuser=True).first()
    return None

def showcase_list_view(request):
    """Listado general de vitrinas con resumen de ocupación (vista pública)."""
    showcases = Showcase.objects.prefetch_related('slots__assignments').all()
    
    showcase_data = []
    for s in showcases:
        total_slots = s.slots.filter(is_active=True).count()
        occupied_slots = SlotAssignment.objects.filter(slot__showcase=s, is_active=True).count()
        free_slots = total_slots - occupied_slots
        occupancy_rate = (occupied_slots / total_slots * 100) if total_slots > 0 else 0
        
        showcase_data.append({
            'showcase': s,
            'total_slots': total_slots,
            'occupied_slots': occupied_slots,
            'free_slots': free_slots,
            'occupancy_rate': occupancy_rate
        })

    return render(request, 'showcases/list.html', {'showcases': showcase_data})

def showcase_create_view(request):
    """Creación de una vitrina con generación automática de la cuadrícula de slots."""
    user = _get_request_user(request)
    if not user:
        return redirect(f"{settings.LOGIN_URL}?next={request.path}")

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip().upper()
        total_spaces_str = request.POST.get('total_spaces', '').strip()
        try:
            total_rows = int(request.POST.get('total_rows', 4))
            total_columns = int(request.POST.get('total_columns', 8))
        except (ValueError, TypeError):
            total_rows = 4
            total_columns = 8

        if total_spaces_str:
            try:
                spaces_val = int(total_spaces_str)
                if spaces_val > 0 and spaces_val != (total_rows * total_columns):
                    if spaces_val % 4 == 0 and spaces_val >= 4:
                        total_rows = 4
                        total_columns = spaces_val // 4
                    elif spaces_val % 3 == 0 and spaces_val >= 3:
                        total_rows = 3
                        total_columns = spaces_val // 3
                    elif spaces_val % 2 == 0 and spaces_val >= 2:
                        total_rows = 2
                        total_columns = spaces_val // 2
                    else:
                        total_rows = 1
                        total_columns = spaces_val
            except (ValueError, TypeError):
                pass

        description = request.POST.get('description', '').strip()
        contact_whatsapp = request.POST.get('contact_whatsapp', '+56912345678').strip()

        if not name or not code:
            messages.error(request, "Nombre y código de vitrina son obligatorios.")
            return render(request, 'showcases/create.html')

        if Showcase.objects.filter(code=code).exists():
            messages.error(request, f"Ya existe una vitrina con el código '{code}'.")
            return render(request, 'showcases/create.html')

        showcase, slots_count = ShowcaseService.create_showcase(
            name=name,
            code=code,
            total_rows=total_rows,
            total_columns=total_columns,
            description=description,
            contact_whatsapp=contact_whatsapp
        )

        messages.success(request, f"Vitrina '{showcase.name}' creada con éxito con {slots_count} slots y QRs permanentes.")
        return redirect('showcase_grid', showcase_id=showcase.id)

    return render(request, 'showcases/create.html')

def showcase_grid_view(request, showcase_id):
    """Visualización interactiva de la cuadrícula física de la vitrina (vista pública)."""
    showcase = get_object_or_404(Showcase, id=showcase_id)
    matrix = ShowcaseService.get_showcase_matrix(showcase)
    
    # Cartas disponibles en inventario para asignar
    available_items = InventoryItem.objects.filter(
        status=InventoryItem.Status.IN_STOCK
    ).select_related('print__card').order_by('print__card__name')

    total_slots = showcase.slots.filter(is_active=True).count()
    occupied_count = SlotAssignment.objects.filter(slot__showcase=showcase, is_active=True).count()

    context = {
        'showcase': showcase,
        'matrix': matrix,
        'available_items': available_items,
        'total_slots': total_slots,
        'occupied_count': occupied_count,
        'free_count': total_slots - occupied_count,
    }
    return render(request, 'showcases/grid.html', context)

@login_required
def slot_assign_view(request, slot_id):
    """Asignación de una carta física a un slot."""
    slot = get_object_or_404(ShowcaseSlot, id=slot_id)
    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        notes = request.POST.get('notes', '').strip()
        item = get_object_or_404(InventoryItem, id=item_id)

        try:
            ShowcaseService.assign_item_to_slot(slot=slot, item=item, user=request.user, notes=notes)
            messages.success(request, f"Carta {item.sku} asignada con éxito al slot {slot.visible_code}.")
        except Exception as e:
            messages.error(request, f"Error al asignar: {e}")

    return redirect('showcase_grid', showcase_id=slot.showcase_id)

@login_required
def slot_unassign_view(request, slot_id):
    """Retiro de una carta física de un slot."""
    slot = get_object_or_404(ShowcaseSlot, id=slot_id)
    if request.method == 'POST':
        reason = request.POST.get('reason', 'Retiro manual de vitrina').strip()
        item = ShowcaseService.unassign_slot(slot=slot, user=request.user, reason=reason)
        if item:
            messages.success(request, f"Carta {item.sku} retirada del slot {slot.visible_code} y devuelta a bodega.")
        else:
            messages.info(request, "El slot ya se encontraba vacío.")

    return redirect('showcase_grid', showcase_id=slot.showcase_id)

def download_slot_qr_view(request, slot_id):
    """Descarga de la etiqueta QR individual de un slot en PNG."""
    slot = get_object_or_404(ShowcaseSlot, id=slot_id)
    buffer = QRGeneratorService.generate_slot_qr_image(slot)
    
    response = HttpResponse(buffer.getvalue(), content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename="QR_{slot.visible_code}.png"'
    return response

@login_required
def download_showcase_sheet_view(request, showcase_id):
    """Descarga de la hoja completa A4 con todos los códigos QR de la vitrina en PNG/PDF."""
    showcase = get_object_or_404(Showcase, id=showcase_id)
    buffer = QRGeneratorService.generate_showcase_sheet_a4(showcase)

    response = HttpResponse(buffer.getvalue(), content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename="Hoja_A4_Vitrinas_{showcase.code}.png"'
    return response

def showcase_edit_view(request, showcase_id):
    """Edición de vitrina y ajuste dinámico de dimensiones (filas x columnas o espacios totales)."""
    user = _get_request_user(request)
    if not user:
        return redirect(f"{settings.LOGIN_URL}?next={request.path}")

    showcase = get_object_or_404(Showcase, id=showcase_id)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        contact_whatsapp = request.POST.get('contact_whatsapp', '').strip()
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('is_active') == '1'
        total_spaces_str = request.POST.get('total_spaces', '').strip()

        try:
            total_rows = int(request.POST.get('total_rows', showcase.total_rows))
            total_columns = int(request.POST.get('total_columns', showcase.total_columns))
        except (ValueError, TypeError):
            total_rows = showcase.total_rows
            total_columns = showcase.total_columns

        # Si el usuario ingresó o seleccionó una cantidad total de espacios directa
        if total_spaces_str:
            try:
                spaces_val = int(total_spaces_str)
                if spaces_val > 0 and spaces_val != (total_rows * total_columns):
                    if spaces_val % 4 == 0 and spaces_val >= 4:
                        total_rows = 4
                        total_columns = spaces_val // 4
                    elif spaces_val % 3 == 0 and spaces_val >= 3:
                        total_rows = 3
                        total_columns = spaces_val // 3
                    elif spaces_val % 2 == 0 and spaces_val >= 2:
                        total_rows = 2
                        total_columns = spaces_val // 2
                    else:
                        total_rows = 1
                        total_columns = spaces_val
            except (ValueError, TypeError):
                pass

        if not name:
            messages.error(request, "El nombre de la vitrina es obligatorio.")
            return render(request, 'showcases/edit.html', {'showcase': showcase})

        showcase.name = name
        showcase.contact_whatsapp = contact_whatsapp
        showcase.description = description
        showcase.is_active = is_active
        showcase.save()

        # Ajustar dimensiones de la cuadrícula si cambiaron filas o columnas
        if total_rows != showcase.total_rows or total_columns != showcase.total_columns:
            active_count, deact_count = ShowcaseService.update_showcase_grid(
                showcase=showcase,
                new_rows=total_rows,
                new_cols=total_columns,
                user=user
            )
            messages.success(
                request,
                f"Dimensiones de vitrina actualizadas: {total_rows} filas x {total_columns} columnas ({active_count} espacios activos)."
            )
        else:
            messages.success(request, f"Vitrina '{showcase.name}' actualizada con éxito.")

        return redirect('showcase_grid', showcase_id=showcase.id)

    return render(request, 'showcases/edit.html', {'showcase': showcase})

def showcase_delete_view(request, showcase_id):
    """Eliminación controlada de vitrina, liberando cartas asociadas a bodega."""
    user = _get_request_user(request)
    if not user:
        return redirect(f"{settings.LOGIN_URL}?next={request.path}")

    showcase = get_object_or_404(Showcase, id=showcase_id)

    if request.method == 'POST':
        name = showcase.name
        with transaction.atomic():
            # 1. Desasignar cartas físicas activas y devolverlas a bodega
            for slot in showcase.slots.all():
                if slot.current_assignment:
                    ShowcaseService.unassign_slot(slot, user=user, reason="Vitrina eliminada")
            # 2. Limpiar registros de asignación asociados a los slots de esta vitrina
            SlotAssignment.objects.filter(slot__showcase=showcase).delete()
            # 3. Eliminar la vitrina física y sus slots en cascada
            showcase.delete()

        messages.success(request, f"Vitrina '{name}' eliminada correctamente. Las cartas que contenía fueron devueltas a bodega.")
        return redirect('showcase_list')

    return render(request, 'showcases/confirm_delete.html', {'showcase': showcase})


def showcase_quick_intake_view(request):
    """
    Asistente unificado de ingreso rápido a vitrina:
    Buscador YGOPRODeck -> Autoselección de variante/rareza -> Cotización automática USD/CLP
    -> Datos de dueño y transferencia directa -> Asignación directa a espacio de vitrina.
    """
    user = _get_request_user(request)
    if not user:
        return redirect(f"{settings.LOGIN_URL}?next={request.path}")

    config = PricingService.get_active_config()

    # Slot preseleccionado opcional vía query params
    slot_id = request.GET.get('slot_id')
    token = request.GET.get('token')
    showcase_id = request.GET.get('showcase_id')

    selected_slot = None
    if token:
        selected_slot = ShowcaseSlot.objects.filter(qr_token=token, is_active=True).select_related('showcase').first()
    elif slot_id:
        selected_slot = ShowcaseSlot.objects.filter(id=slot_id, is_active=True).select_related('showcase').first()

    selected_showcase = selected_slot.showcase if selected_slot else None
    if not selected_showcase and showcase_id:
        selected_showcase = Showcase.objects.filter(id=showcase_id, is_active=True).first()

    if request.method == 'POST':
        # 1. Datos de Carta
        name = request.POST.get('name', '').strip()
        ygoprodeck_id = request.POST.get('ygoprodeck_id') or None
        card_type = request.POST.get('card_type', '').strip()
        description = request.POST.get('description', '').strip()
        race = request.POST.get('race', '').strip()
        attribute = request.POST.get('attribute', '').strip()
        atk = request.POST.get('atk') or None
        def_points = request.POST.get('def_points') or None
        level = request.POST.get('level') or None

        # 2. Variante / Set / Rareza
        print_code = request.POST.get('print_code', '').strip().upper()
        set_name = request.POST.get('set_name', '').strip()
        rarity = request.POST.get('rarity', '').strip()
        edition = request.POST.get('edition', CardPrint.Edition.FIRST_EDITION)
        language = request.POST.get('language', CardPrint.Language.EN)
        image_url = request.POST.get('image_url', '').strip()
        uploaded_image = request.FILES.get('card_image')

        # 3. Precios y Cotización
        ref_usd_str = request.POST.get('ref_usd', '0').strip()
        cash_price_str = request.POST.get('cash_price', '0').strip()
        card_price_str = request.POST.get('card_price', '0').strip()

        # 4. Datos del Dueño y Transferencia (Consignación)
        owner_name = request.POST.get('owner_name', 'Tienda').strip() or 'Tienda'
        owner_phone = request.POST.get('owner_phone', '').strip()
        owner_rut = request.POST.get('owner_rut', '').strip()
        owner_bank = request.POST.get('owner_bank', '').strip()
        owner_account_type = request.POST.get('owner_account_type', '').strip()
        owner_account_number = request.POST.get('owner_account_number', '').strip()
        owner_email = request.POST.get('owner_email', '').strip()
        owner_payout_str = request.POST.get('owner_payout_amount', '').strip()

        # 5. Inventario Físico y Slot
        condition = request.POST.get('condition', InventoryItem.Condition.NEAR_MINT)
        acquisition_cost_str = request.POST.get('acquisition_cost', '').strip()
        target_slot_id = request.POST.get('slot_id')

        if not name or not print_code or not set_name or not rarity:
            messages.error(request, "Nombre, código de impresión, set y rareza son obligatorios.")
            return redirect(request.get_full_path())

        if not target_slot_id:
            messages.error(request, "Debes seleccionar un espacio (slot) de vitrina.")
            return redirect(request.get_full_path())

        slot = get_object_or_404(ShowcaseSlot.objects.select_related('showcase'), id=target_slot_id, is_active=True)

        try:
            with transaction.atomic():
                # A. Crear o actualizar Carta base
                clean_name = slugify(name)
                card_defaults = {
                    'clean_name': clean_name,
                    'card_type': card_type,
                    'description': description,
                    'race': race,
                    'attribute': attribute,
                    'atk': int(atk) if atk else None,
                    'def_points': int(def_points) if def_points else None,
                    'level': int(level) if level else None,
                }
                if ygoprodeck_id and str(ygoprodeck_id).isdigit():
                    card_defaults['ygoprodeck_id'] = int(ygoprodeck_id)
                    card, _ = Card.objects.update_or_create(
                        ygoprodeck_id=int(ygoprodeck_id),
                        defaults={'name': name, **card_defaults}
                    )
                else:
                    card, _ = Card.objects.update_or_create(name=name, defaults=card_defaults)

                # B. Crear o actualizar CardPrint
                print_defaults = {
                    'set_name': set_name,
                    'image_url': image_url or '',
                }
                card_print, created = CardPrint.objects.get_or_create(
                    card=card,
                    print_code=print_code,
                    rarity=rarity,
                    edition=edition,
                    language=language,
                    defaults=print_defaults
                )
                if not created and image_url and not card_print.image_url:
                    card_print.image_url = image_url
                    card_print.save(update_fields=['image_url'])

                if uploaded_image:
                    card_print.image = uploaded_image
                    card_print.save(update_fields=['image'])

                # C. Precios y Cotización
                ref_usd = parse_decimal_input(ref_usd_str, default=Decimal('0'))
                cash_price = parse_decimal_input(cash_price_str, default=Decimal('0'))
                card_price = parse_decimal_input(card_price_str, default=Decimal('0'))

                # Si no se ingresaron precios finales pero sí USD, calcularlos
                if (cash_price <= 0 or card_price <= 0) and ref_usd > 0:
                    c_cash, c_card = PricingService.calculate_prices_from_usd(ref_usd, config)
                    if cash_price <= 0:
                        cash_price = c_cash
                    if card_price <= 0:
                        card_price = c_card

                PricingService.save_quote(
                    card_print=card_print,
                    reference_price_usd=ref_usd if ref_usd > 0 else None,
                    source=PriceQuote.Source.TCGPLAYER_DIRECT if ref_usd > 0 else PriceQuote.Source.MANUAL,
                    custom_cash_price=cash_price if cash_price > 0 else None,
                    custom_card_price=card_price if card_price > 0 else None,
                    config=config
                )

                # D. Crear InventoryItem físico con datos de dueño y bancarios
                owner_payout = parse_decimal_input(owner_payout_str, default=None) if owner_payout_str else None
                acq_cost = parse_decimal_input(acquisition_cost_str, default=owner_payout or Decimal('0'))

                item = InventoryItem.objects.create(
                    print=card_print,
                    condition=condition,
                    acquisition_cost=acq_cost,
                    status=InventoryItem.Status.IN_STOCK,
                    location=f"{slot.showcase.name} - {slot.visible_code}",
                    notes=f"Ingresado rápido a vitrina {slot.visible_code}",
                    owner_name=owner_name,
                    owner_phone=owner_phone,
                    owner_rut=owner_rut,
                    owner_bank=owner_bank,
                    owner_account_type=owner_account_type,
                    owner_account_number=owner_account_number,
                    owner_email=owner_email,
                    owner_payout_amount=owner_payout
                )

                # E. Asignar directamente al slot de vitrina
                if slot.current_assignment:
                    ShowcaseService.unassign_slot(slot, user=user, reason="Reemplazo por ingreso rápido")

                ShowcaseService.assign_item_to_slot(
                    slot=slot,
                    item=item,
                    user=user,
                    notes="Asignación directa desde ingreso rápido"
                )

            messages.success(
                request,
                f"¡Carta '{card.name}' [{card_print.print_code}] ({card_print.rarity}) publicada exitosamente en el espacio {slot.visible_code} de {slot.showcase.name}!"
            )
            return redirect('public_slot_detail', qr_token=slot.qr_token)

        except Exception as e:
            messages.error(request, f"Ocurrió un error al ingresar la carta: {e}")
            return redirect(request.get_full_path())

    # GET: Cargar vitrinas y slots disponibles
    showcases = Showcase.objects.filter(is_active=True).order_by('name')
    occupied_slot_ids = SlotAssignment.objects.filter(is_active=True).values_list('slot_id', flat=True)
    all_active_slots = ShowcaseSlot.objects.filter(is_active=True).select_related('showcase').order_by('showcase__name', 'slot_number')

    slot_options = []
    for s in all_active_slots:
        is_occupied = s.id in occupied_slot_ids
        slot_options.append({
            'slot': s,
            'is_occupied': is_occupied,
            'is_selected': selected_slot and selected_slot.id == s.id,
        })

    context = {
        'showcases': showcases,
        'slot_options': slot_options,
        'selected_slot': selected_slot,
        'selected_showcase': selected_showcase,
        'editions': CardPrint.Edition.choices,
        'languages': CardPrint.Language.choices,
        'conditions': InventoryItem.Condition.choices,
        'config': config,
    }
    return render(request, 'showcases/quick_intake.html', context)


