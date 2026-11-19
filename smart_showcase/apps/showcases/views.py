from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from apps.inventory.models import InventoryItem
from apps.showcases.models import Showcase, ShowcaseSlot, SlotAssignment
from apps.showcases.services import ShowcaseService
from apps.showcases.qr_generator import QRGeneratorService

@login_required
def showcase_list_view(request):
    """Listado general de vitrinas con resumen de ocupación."""
    showcases = Showcase.objects.prefetch_related('slots__assignments').all()
    
    showcase_data = []
    for s in showcases:
        total_slots = s.slots.count()
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

@login_required
def showcase_create_view(request):
    """Creación de una vitrina con generación automática de la cuadrícula de slots."""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip().upper()
        total_rows = int(request.POST.get('total_rows', 4))
        total_columns = int(request.POST.get('total_columns', 8))
        description = request.POST.get('description', '').strip()

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
            description=description
        )

        messages.success(request, f"Vitrina '{showcase.name}' creada con éxito con {slots_count} slots y QRs permanentes.")
        return redirect('showcase_grid', showcase_id=showcase.id)

    return render(request, 'showcases/create.html')

@login_required
def showcase_grid_view(request, showcase_id):
    """Visualización interactiva de la cuadrícula física de la vitrina."""
    showcase = get_object_or_404(Showcase, id=showcase_id)
    matrix = ShowcaseService.get_showcase_matrix(showcase)
    
    # Cartas disponibles en inventario para asignar
    available_items = InventoryItem.objects.filter(
        status=InventoryItem.Status.IN_STOCK
    ).select_related('print__card').order_by('print__card__name')

    total_slots = showcase.slots.count()
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
