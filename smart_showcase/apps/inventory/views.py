from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from apps.catalog.models import CardPrint
from apps.inventory.models import InventoryItem, InventoryMovement
from apps.inventory.services import InventoryService

@login_required
def inventory_list_view(request):
    """Listado del inventario con métricas ejecutivas y filtros."""
    status_filter = request.GET.get('status', '').strip()
    condition_filter = request.GET.get('condition', '').strip()
    q = request.GET.get('q', '').strip()

    items = InventoryItem.objects.select_related('print__card').prefetch_related('slot_assignments')

    if status_filter:
        items = items.filter(status=status_filter)
    if condition_filter:
        items = items.filter(condition=condition_filter)
    if q:
        items = items.filter(
            Q(sku__icontains=q) |
            Q(print__card__name__icontains=q) |
            Q(print__print_code__icontains=q) |
            Q(location__icontains=q)
        )

    # Métricas agregadas
    total_count = InventoryItem.objects.count()
    in_stock_count = InventoryItem.objects.filter(status=InventoryItem.Status.IN_STOCK).count()
    in_showcase_count = InventoryItem.objects.filter(status=InventoryItem.Status.IN_SHOWCASE).count()
    total_valuation = InventoryItem.objects.filter(status__in=[InventoryItem.Status.IN_STOCK, InventoryItem.Status.IN_SHOWCASE]).aggregate(
        total=Sum('acquisition_cost')
    )['total'] or Decimal('0.00')

    context = {
        'items': items,
        'status_filter': status_filter,
        'condition_filter': condition_filter,
        'q': q,
        'statuses': InventoryItem.Status.choices,
        'conditions': InventoryItem.Condition.choices,
        'metrics': {
            'total_count': total_count,
            'in_stock_count': in_stock_count,
            'in_showcase_count': in_showcase_count,
            'total_valuation': total_valuation
        }
    }
    return render(request, 'inventory/list.html', context)

@login_required
def inventory_create_view(request):
    """Alta de cartas físicas individuales o en lote."""
    card_print_id = request.GET.get('print_id')
    selected_print = None
    if card_print_id:
        selected_print = get_object_or_404(CardPrint.objects.select_related('card'), id=card_print_id)

    if request.method == 'POST':
        print_id = request.POST.get('print_id')
        condition = request.POST.get('condition', InventoryItem.Condition.NEAR_MINT)
        acquisition_cost = Decimal(request.POST.get('acquisition_cost', '0'))
        quantity = int(request.POST.get('quantity', '1'))
        location = request.POST.get('location', 'Bodega Principal').strip()
        notes = request.POST.get('notes', '').strip()

        target_print = get_object_or_404(CardPrint, id=print_id)

        if quantity == 1:
            item = InventoryService.create_item(
                card_print=target_print,
                condition=condition,
                acquisition_cost=acquisition_cost,
                location=location,
                notes=notes,
                user=request.user
            )
            messages.success(request, f"Ejemplar {item.sku} ({target_print.card.name}) registrado correctamente.")
        else:
            items = InventoryService.bulk_create_items(
                card_print=target_print,
                quantity=quantity,
                condition=condition,
                acquisition_cost=acquisition_cost,
                location=location,
                notes=notes,
                user=request.user
            )
            messages.success(request, f"Se crearon con éxito {len(items)} ejemplares de {target_print.card.name}.")

        return redirect('inventory_list')

    prints = CardPrint.objects.select_related('card').order_by('card__name', 'print_code')
    return render(request, 'inventory/create.html', {
        'prints': prints,
        'selected_print': selected_print,
        'conditions': InventoryItem.Condition.choices,
    })

@login_required
def inventory_detail_view(request, item_id):
    """Detalle de un ejemplar físico con su historial de movimientos."""
    item = get_object_or_404(InventoryItem.objects.select_related('print__card'), id=item_id)
    movements = item.movements.select_related('user').order_by('-created_at')
    
    return render(request, 'inventory/detail.html', {
        'item': item,
        'movements': movements,
        'statuses': InventoryItem.Status.choices
    })

@login_required
def inventory_update_status_view(request, item_id):
    """Actualización rápida de estado o ubicación física."""
    if request.method == 'POST':
        item = get_object_or_404(InventoryItem, id=item_id)
        new_status = request.POST.get('new_status')
        new_location = request.POST.get('new_location', '').strip()
        reason = request.POST.get('reason', '').strip()

        InventoryService.update_item_status(
            item=item,
            new_status=new_status,
            new_location=new_location if new_location else None,
            user=request.user,
            reason=reason
        )
        messages.success(request, f"Estado del ítem {item.sku} actualizado a {item.get_status_display()}.")
        return redirect('inventory_detail', item_id=item.id)

    return redirect('inventory_list')
