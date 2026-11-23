import json
import urllib.request
from decimal import Decimal
from typing import Optional, Dict, Any, List, Tuple
from apps.catalog.models import Card, CardPrint
from apps.pricing.models import PriceQuote, PricingRuleConfig
from apps.pricing.services import PricingService

class CardPriceAPIService:
    """
    Servicio de obtención automática de precios de mercado en USD (TCGplayer / YGOPRODeck).
    Permite obtener el precio oficial por set/edición o por carta base sin ingreso manual.
    """

    API_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"
    HEADERS = {'User-Agent': 'SubarashiiSmartShowcase/1.0 (Store Management)'}

    @classmethod
    def _fetch_card_raw_data(cls, card: Card) -> Optional[Dict[str, Any]]:
        """Consulta la API de YGOPRODeck por ID o por nombre de carta."""
        try:
            if card.ygoprodeck_id:
                url = f"{cls.API_URL}?id={card.ygoprodeck_id}"
            else:
                encoded_name = urllib.parse.quote(card.name)
                url = f"{cls.API_URL}?name={encoded_name}"

            req = urllib.request.Request(url, headers=cls.HEADERS)
            with urllib.request.urlopen(req, timeout=8) as res:
                data = json.loads(res.read().decode('utf-8'))
                cards = data.get('data', [])
                if cards:
                    return cards[0]
        except Exception as e:
            print(f"[CardPriceAPIService] Error consultando API para '{card.name}': {e}")
        return None

    @classmethod
    def extract_usd_price_for_print(cls, card_data: Dict[str, Any], print_code: str) -> Optional[Decimal]:
        """
        Extrae el precio de mercado en USD para un código de impresión específico.
        Prioriza el set_price de la expansión exacta; si no está disponible,
        utiliza el tcgplayer_price general de la carta.
        """
        norm_code = print_code.strip().upper()
        card_sets = card_data.get('card_sets', [])

        # 1. Búsqueda exacta por código de set (ej: LOB-005, RA01-EN001)
        for s in card_sets:
            scode = s.get('set_code', '').strip().upper()
            if scode == norm_code:
                sprice = s.get('set_price')
                if sprice:
                    try:
                        val = Decimal(str(sprice))
                        if val > 0:
                            return val
                    except Exception:
                        pass

        # 2. Búsqueda flexible (sin código de región intermedio, ej: LOB-EN005 vs LOB-005)
        for s in card_sets:
            scode = s.get('set_code', '').strip().upper()
            if '-' in scode and '-' in norm_code:
                set_a, num_a = scode.split('-', 1)
                set_b, num_b = norm_code.split('-', 1)
                num_a_digits = ''.join(filter(str.isdigit, num_a))
                num_b_digits = ''.join(filter(str.isdigit, num_b))
                if set_a == set_b and num_a_digits and num_a_digits == num_b_digits:
                    sprice = s.get('set_price')
                    if sprice:
                        try:
                            val = Decimal(str(sprice))
                            if val > 0:
                                return val
                        except Exception:
                            pass

        # 3. Fallback: Precio de mercado TCGplayer general de la carta
        prices_list = card_data.get('card_prices', [])
        if prices_list:
            p = prices_list[0]
            tcg_price = p.get('tcgplayer_price') or p.get('coolstuffinc_price') or p.get('ebay_price')
            if tcg_price:
                try:
                    val = Decimal(str(tcg_price))
                    if val > 0:
                        return val
                except Exception:
                    pass

        return None

    @classmethod
    def get_usd_price_for_card_and_code(cls, ygoprodeck_id: Optional[int] = None, card_name: str = "", print_code: str = "") -> Optional[Decimal]:
        """Consulta la API de precios para un ID/Nombre y código de set dado."""
        import urllib.parse
        try:
            if ygoprodeck_id:
                url = f"{cls.API_URL}?id={ygoprodeck_id}"
            elif card_name:
                url = f"{cls.API_URL}?name={urllib.parse.quote(card_name)}"
            else:
                return None

            req = urllib.request.Request(url, headers=cls.HEADERS)
            with urllib.request.urlopen(req, timeout=8) as res:
                data = json.loads(res.read().decode('utf-8'))
                cards = data.get('data', [])
                if cards:
                    return cls.extract_usd_price_for_print(cards[0], print_code)
        except Exception as e:
            print(f"[CardPriceAPIService] Error en consulta rápida de precio USD: {e}")
        return None

    @classmethod
    def sync_quote_for_print(
        cls,
        card_print: CardPrint,
        config: Optional[PricingRuleConfig] = None
    ) -> Optional[PriceQuote]:
        """
        Obtiene el precio de mercado en USD vía API para una impresión y genera
        automáticamente la cotización vigente (PriceQuote) con conversión a CLP.
        """
        card_data = cls._fetch_card_raw_data(card_print.card)
        if not card_data:
            return None

        usd_price = cls.extract_usd_price_for_print(card_data, card_print.print_code)
        if not usd_price:
            return None

        quote = PricingService.save_quote(
            card_print=card_print,
            reference_price_usd=usd_price,
            source=PriceQuote.Source.TCGPLAYER_DIRECT,
            config=config
        )
        return quote

    @classmethod
    def sync_all_prints_for_card(
        cls,
        card: Card,
        config: Optional[PricingRuleConfig] = None
    ) -> int:
        """
        Sincroniza y cotiza automáticamente en 1 sola llamada API todas las impresiones
        asociadas a una carta. Retorna la cantidad de impresiones cotizadas con éxito.
        """
        card_data = cls._fetch_card_raw_data(card)
        if not card_data:
            return 0

        synced_count = 0
        prints = card.prints.all()
        for p in prints:
            usd_price = cls.extract_usd_price_for_print(card_data, p.print_code)
            if usd_price and usd_price > 0:
                PricingService.save_quote(
                    card_print=p,
                    reference_price_usd=usd_price,
                    source=PriceQuote.Source.TCGPLAYER_DIRECT,
                    config=config
                )
                synced_count += 1

        return synced_count
