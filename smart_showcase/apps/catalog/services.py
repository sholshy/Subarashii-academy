from typing import List, Optional, Tuple
from decimal import Decimal
from django.db import transaction
from django.utils.text import slugify
from apps.catalog.models import Card, CardPrint
from integrations.base import BaseCatalogProvider, CatalogCardData
from integrations.ygoprodeck.client import YGOPRODeckClient

class CatalogService:
    def __init__(self, provider: Optional[BaseCatalogProvider] = None):
        self.provider = provider or YGOPRODeckClient()

    def search_local_cards(self, query: str = "", set_code: str = "") -> List[Card]:
        qs = Card.objects.all().prefetch_related('prints')
        if query:
            qs = qs.filter(name__icontains=query)
        if set_code:
            qs = qs.filter(prints__print_code__icontains=set_code).distinct()
        return list(qs)

    def search_remote_cards(self, query: str = "") -> List[CatalogCardData]:
        if not query:
            return []
        return self.provider.search_by_name(query)

    @transaction.atomic
    def import_card_from_ygoprodeck_data(self, data: CatalogCardData) -> Tuple[Card, int]:
        """
        Crea o actualiza la carta base e importa todas sus impresiones (sets) asociadas.
        Retorna (card, prints_created_count).
        """
        clean_name = slugify(data.name)
        card, created = Card.objects.update_or_create(
            ygoprodeck_id=data.ygoprodeck_id,
            defaults={
                'name': data.name,
                'clean_name': clean_name,
                'card_type': data.card_type or '',
                'description': data.description or '',
                'race': data.race or '',
                'attribute': data.attribute or '',
                'atk': data.atk,
                'def_points': data.def_points,
                'level': data.level,
                'scale': data.scale,
                'link_val': data.link_val,
                'archetype': data.archetype or '',
            }
        )

        prints_created = 0
        card_sets = data.card_sets or []

        # Si YGOPRODeck no trajo sets pero sí una imagen, crear al menos una impresión base
        if not card_sets:
            # Creación de impresión genérica si no hay set detallado
            _, p_created = CardPrint.objects.get_or_create(
                card=card,
                print_code="PROMO-GEN",
                rarity="Common",
                edition=CardPrint.Edition.UNLIMITED,
                language=CardPrint.Language.EN,
                defaults={
                    'set_name': 'Promo / Desconocido',
                    'image_url': data.image_url or ''
                }
            )
            if p_created:
                prints_created += 1

        for s in card_sets:
            set_code = s.get('set_code', '').strip()
            if not set_code:
                continue

            set_name = s.get('set_name', 'Desconocido')
            rarity = s.get('set_rarity', 'Common')
            rarity_code = s.get('set_rarity_code', '')

            # Detectar idioma por sufijo de código (ej: LOB-E001 -> EN, LOB-S001 -> ES)
            language = CardPrint.Language.EN
            if '-' in set_code:
                prefix_part = set_code.split('-')[1]
                if prefix_part.startswith('S') or prefix_part.startswith('SP'):
                    language = CardPrint.Language.ES
                elif prefix_part.startswith('JP') or prefix_part.startswith('JA'):
                    language = CardPrint.Language.JP
                elif prefix_part.startswith('FR'):
                    language = CardPrint.Language.FR
                elif prefix_part.startswith('DE'):
                    language = CardPrint.Language.DE
                elif prefix_part.startswith('IT'):
                    language = CardPrint.Language.IT
                elif prefix_part.startswith('PT'):
                    language = CardPrint.Language.PT

            # Por defecto las expansiones estándar se registran como 1st Edition o Unlimited
            edition = CardPrint.Edition.FIRST_EDITION if '1st' in s.get('set_edition', '').lower() else CardPrint.Edition.UNLIMITED

            print_obj, p_created = CardPrint.objects.get_or_create(
                card=card,
                print_code=set_code,
                rarity=rarity,
                edition=edition,
                language=language,
                defaults={
                    'set_name': set_name,
                    'rarity_code': rarity_code,
                    'image_url': data.image_url or ''
                }
            )
            if p_created:
                prints_created += 1

            # Auto-cotización inicial en USD si el set incluye set_price de TCGplayer
            set_price_str = s.get('set_price')
            if set_price_str:
                try:
                    ref_usd = Decimal(str(set_price_str))
                    if ref_usd > 0:
                        from apps.pricing.services import PricingService
                        from apps.pricing.models import PriceQuote
                        PricingService.save_quote(
                            card_print=print_obj,
                            reference_price_usd=ref_usd,
                            source=PriceQuote.Source.TCGPLAYER_DIRECT
                        )
                except Exception:
                    pass

        return card, prints_created

    def import_by_ygoprodeck_id(self, ygoprodeck_id: int) -> Optional[Tuple[Card, int]]:
        card_data = self.provider.get_by_id(ygoprodeck_id)
        if not card_data:
            return None
        return self.import_card_from_ygoprodeck_data(card_data)

    @transaction.atomic
    def create_custom_card(self, name: str, card_type: str = "", description: str = "", **kwargs) -> Card:
        """Permite crear cartas manualmente sin depender de APIs externas."""
        clean_name = slugify(name)
        card = Card.objects.create(
            name=name,
            clean_name=clean_name,
            card_type=card_type,
            description=description,
            atk=kwargs.get('atk'),
            def_points=kwargs.get('def_points'),
            level=kwargs.get('level'),
            attribute=kwargs.get('attribute', ''),
            race=kwargs.get('race', ''),
            archetype=kwargs.get('archetype', '')
        )
        return card

    @transaction.atomic
    def create_custom_print(
        self,
        card: Card,
        print_code: str,
        set_name: str,
        rarity: str,
        edition: str = CardPrint.Edition.FIRST_EDITION,
        language: str = CardPrint.Language.EN,
        image_url: str = "",
        tcgplayer_product_id: Optional[str] = None
    ) -> CardPrint:
        """Crea una impresión manual de una carta."""
        card_print, _ = CardPrint.objects.get_or_create(
            card=card,
            print_code=print_code,
            rarity=rarity,
            edition=edition,
            language=language,
            defaults={
                'set_name': set_name,
                'image_url': image_url,
                'tcgplayer_product_id': tcgplayer_product_id
            }
        )
        return card_print
