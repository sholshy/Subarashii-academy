from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from apps.catalog.models import Card, CardPrint
from apps.catalog.services import CatalogService

catalog_service = CatalogService()

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

@login_required
def catalog_import_card_view(request, ygoprodeck_id):
    """Importa una carta desde YGOPRODeck a la base de datos local."""
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

@login_required
def catalog_card_create_view(request):
    """Creación manual de una carta e impresión sin depender de APIs."""
    if request.method == 'POST':
        name = request.form_data = request.POST.get('name', '').strip()
        card_type = request.POST.get('card_type', '').strip()
        description = request.POST.get('description', '').strip()
        atk = request.POST.get('atk') or None
        def_points = request.POST.get('def_points') or None
        level = request.POST.get('level') or None
        race = request.POST.get('race', '').strip()
        attribute = request.POST.get('attribute', '').strip()

        print_code = request.POST.get('print_code', '').strip()
        set_name = request.POST.get('set_name', '').strip()
        rarity = request.POST.get('rarity', '').strip()

        if not name or not print_code or not set_name or not rarity:
            messages.error(request, "Nombre, código de impresión, set y rareza son obligatorios.")
            return render(request, 'catalog/create.html')

        card = catalog_service.create_custom_card(
            name=name,
            card_type=card_type,
            description=description,
            atk=int(atk) if atk else None,
            def_points=int(def_points) if def_points else None,
            level=int(level) if level else None,
            race=race,
            attribute=attribute
        )

        catalog_service.create_custom_print(
            card=card,
            print_code=print_code,
            set_name=set_name,
            rarity=rarity,
            edition=request.POST.get('edition', CardPrint.Edition.FIRST_EDITION),
            language=request.POST.get('language', CardPrint.Language.EN),
            image_url=request.POST.get('image_url', '').strip()
        )

        messages.success(request, f"Carta '{card.name}' e impresión creada manualmente con éxito.")
        return redirect('catalog_card_detail', card_id=card.id)

    return render(request, 'catalog/create.html', {
        'editions': CardPrint.Edition.choices,
        'languages': CardPrint.Language.choices,
    })
