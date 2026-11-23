from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.utils.text import slugify
from decimal import Decimal
from apps.catalog.models import Card, CardPrint
from apps.catalog.services import CatalogService

catalog_service = CatalogService()

def _get_request_user(request):
    """Retorna el usuario actual, o en modo local (DEBUG) el usuario admin para facilitar la gestión."""
    if request.user.is_authenticated:
        return request.user
    if getattr(settings, 'DEBUG', False):
        from apps.accounts.models import CustomUser
        return CustomUser.objects.filter(is_superuser=True).first()
    return None

def catalog_list_view(request):
    """Vista principal del catálogo con búsqueda local y remota."""
    query = request.GET.get('q', '').strip()
    set_code = request.GET.get('set_code', '').strip()
    
    cards = catalog_service.search_local_cards(query=query, set_code=set_code)
    
    # Si la petición proviene de HTMX, renderizamos solo la tabla o resultados
    if request.headers.get('HX-Request'):
        return render(request, 'catalog/partials/card_table.html', {'cards': cards, 'query': query})
        
    return render(request, 'catalog/list.html', {
        'cards': cards,
        'query': query,
        'set_code': set_code,
        'total_cards': Card.objects.count(),
        'total_prints': CardPrint.objects.count()
    })

def catalog_card_detail_view(request, card_id):
    """Detalle de una carta con todas sus impresiones."""
    card = get_object_or_404(Card.objects.prefetch_related('prints'), id=card_id)
    return render(request, 'catalog/detail.html', {'card': card})

def catalog_remote_search_view(request):
    """Búsqueda dinámica en YGOPRODeck mediante HTMX."""
    query = request.GET.get('remote_q', '').strip()
    remote_cards = []
    if len(query) >= 3:
        remote_cards = catalog_service.search_remote_cards(query)
    
    return render(request, 'catalog/partials/remote_search_results.html', {
        'remote_cards': remote_cards,
        'query': query
    })

def catalog_api_search_view(request):
    """API endpoint para búsqueda instantánea de cartas y sus variantes en YGOPRODeck y local."""
    query = request.GET.get('q', '').strip()
    if not query or len(query) < 2:
        return JsonResponse({'cards': []})

    results = []
    # 1. Búsqueda remota en YGOPRODeck
    try:
        remote_cards = catalog_service.search_remote_cards(query)
        for c in remote_cards:
            results.append({
                'ygoprodeck_id': c.ygoprodeck_id,
                'name': c.name,
                'card_type': c.card_type or '',
                'description': c.description or '',
                'race': c.race or '',
                'attribute': c.attribute or '',
                'atk': c.atk,
                'def_points': c.def_points,
                'level': c.level,
                'image_url': c.image_url or '',
                'card_sets': c.card_sets or [],
            })
    except Exception as e:
        print(f"[catalog_api_search] Remote error: {e}")

    # 2. Si no hubo resultados remotos (ej. offline o local), buscar en base de datos local
    if not results:
        local_cards = Card.objects.filter(name__icontains=query).prefetch_related('prints')[:15]
        for c in local_cards:
            first_print = c.prints.first()
            sets = []
            for p in c.prints.all():
                sets.append({
                    'set_name': p.set_name,
                    'set_code': p.print_code,
                    'set_rarity': p.rarity,
                    'set_price': ''
                })
            results.append({
                'ygoprodeck_id': c.ygoprodeck_id,
                'name': c.name,
                'card_type': c.card_type or '',
                'description': c.description or '',
                'race': c.race or '',
                'attribute': c.attribute or '',
                'atk': c.atk,
                'def_points': c.def_points,
                'level': c.level,
                'image_url': first_print.display_image_url if first_print else '',
                'card_sets': sets,
            })

    return JsonResponse({'cards': results})


def catalog_api_card_details_view(request, ygoprodeck_id):
    """API endpoint que retorna detalles y todas las variantes/sets de una carta por su ID de YGOPRODeck."""
    try:
        card_data = catalog_service.provider.get_by_id(ygoprodeck_id)
        if card_data:
            return JsonResponse({
                'success': True,
                'card': {
                    'ygoprodeck_id': card_data.ygoprodeck_id,
                    'name': card_data.name,
                    'card_type': card_data.card_type or '',
                    'description': card_data.description or '',
                    'race': card_data.race or '',
                    'attribute': card_data.attribute or '',
                    'atk': card_data.atk,
                    'def_points': card_data.def_points,
                    'level': card_data.level,
                    'image_url': card_data.image_url or '',
                    'card_sets': card_data.card_sets or [],
                }
            })
    except Exception as e:
        print(f"[catalog_api_card_details] Error: {e}")

    return JsonResponse({'success': False, 'error': 'No se encontró la carta en YGOPRODeck.'}, status=404)


def catalog_import_card_view(request, ygoprodeck_id):
    """Importa una carta desde YGOPRODeck a la base de datos local."""
    user = _get_request_user(request)
    if not user:
        return redirect(f"{settings.LOGIN_URL}?next={request.path}")

    if request.method == 'POST':
        result = catalog_service.import_by_ygoprodeck_id(ygoprodeck_id)
        if result:
            card, prints_count = result
            messages.success(request, f"¡Carta '{card.name}' importada con éxito con {prints_count} impresiones!")
            if request.headers.get('HX-Request'):
                return render(request, 'catalog/partials/import_success_badge.html', {'card': card, 'prints_count': prints_count})
            return redirect('catalog_card_detail', card_id=card.id)
        else:
            messages.error(request, "No se pudo obtener información de YGOPRODeck.")
    return redirect('catalog_list')


def catalog_card_create_view(request):
    """Creación e importación de carta y variantes con soporte para foto real y cámara."""
    user = _get_request_user(request)
    if not user:
        return redirect(f"{settings.LOGIN_URL}?next={request.path}")

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        card_type = request.POST.get('card_type', '').strip()
        description = request.POST.get('description', '').strip()
        atk = request.POST.get('atk') or None
        def_points = request.POST.get('def_points') or None
        level = request.POST.get('level') or None
        race = request.POST.get('race', '').strip()
        attribute = request.POST.get('attribute', '').strip()
        ygoprodeck_id = request.POST.get('ygoprodeck_id') or None

        print_code = request.POST.get('print_code', '').strip().upper()
        set_name = request.POST.get('set_name', '').strip()
        rarity = request.POST.get('rarity', '').strip()
        edition = request.POST.get('edition', CardPrint.Edition.FIRST_EDITION)
        language = request.POST.get('language', CardPrint.Language.EN)
        image_url = request.POST.get('image_url', '').strip()

        # Imagen real subida (archivo o captura de cámara)
        uploaded_image = request.FILES.get('card_image')

        # Opciones opcionales de inventario físico
        add_to_inventory = request.POST.get('add_to_inventory') == '1'
        condition = request.POST.get('condition', 'NM')
        acquisition_cost_str = request.POST.get('acquisition_cost', '0').strip()
        location = request.POST.get('location', '').strip() or 'Bodega Principal'
        notes = request.POST.get('notes', '').strip() or 'Ingresado desde creador rápido con foto real'

        if not name or not print_code or not set_name or not rarity:
            messages.error(request, "Nombre, código de impresión, set y rareza son obligatorios.")
            return render(request, 'catalog/create.html', {
                'editions': CardPrint.Edition.choices,
                'languages': CardPrint.Language.choices,
            })

        # 1. Crear o actualizar la carta base
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
        if ygoprodeck_id:
            try:
                card_defaults['ygoprodeck_id'] = int(ygoprodeck_id)
                card, _ = Card.objects.update_or_create(
                    ygoprodeck_id=int(ygoprodeck_id),
                    defaults={'name': name, **card_defaults}
                )
            except Exception:
                card, _ = Card.objects.update_or_create(name=name, defaults=card_defaults)
        else:
            card, _ = Card.objects.update_or_create(name=name, defaults=card_defaults)

        # 2. Crear o actualizar la impresión seleccionada
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

        # Guardar imagen real si fue adjuntada o capturada con cámara
        if uploaded_image:
            card_print.image = uploaded_image
            card_print.save(update_fields=['image'])

        # 3. Ingreso directo a inventario físico si fue solicitado
        if add_to_inventory:
            try:
                from apps.inventory.models import InventoryItem
                cost = Decimal(acquisition_cost_str) if acquisition_cost_str else Decimal('0')
                item = InventoryItem.objects.create(
                    print=card_print,
                    condition=condition,
                    acquisition_cost=cost,
                    status=InventoryItem.Status.IN_STOCK,
                    location=location,
                    notes=notes
                )
                messages.success(request, f"¡Carta '{card.name}' [{print_code}] creada e ingresada a inventario físico (SKU: {item.sku})!")
            except Exception as e_inv:
                messages.success(request, f"¡Carta '{card.name}' [{print_code}] registrada en catálogo! (Aviso inventario: {e_inv})")
        else:
            messages.success(request, f"¡Carta '{card.name}' [{print_code}] ({rarity}) registrada en el catálogo con éxito!")

        return redirect('catalog_card_detail', card_id=card.id)

    return render(request, 'catalog/create.html', {
        'editions': CardPrint.Edition.choices,
        'languages': CardPrint.Language.choices,
    })
