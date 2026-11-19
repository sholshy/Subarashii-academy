import math
from typing import Optional, Tuple, List
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.catalog.models import CardPrint
from apps.pricing.models import PricingRuleConfig, PriceQuote

class PricingService:
    @classmethod
    def get_active_config(cls) -> PricingRuleConfig:
        config = PricingRuleConfig.objects.filter(is_active=True).first()
        if not config:
            config = PricingRuleConfig.objects.create(
                name="Configuración Estándar Subarashii",
                usd_to_clp_rate=Decimal("950.00"),
                commercial_margin_percent=Decimal("25.00"),
                cash_discount_percent=Decimal("5.00"),
                card_processing_fee_percent=Decimal("2.95"),
                tax_percent=Decimal("19.00"),
                rounding_unit=100
            )
        return config

    @classmethod
    def round_to_unit(cls, value: Decimal, unit: int = 100) -> Decimal:
        if unit <= 0:
            return value.quantize(Decimal('1'))
        val_float = float(value)
        rounded = round(val_float / unit) * unit
        return Decimal(str(int(rounded)))

    @classmethod
    def calculate_prices_from_usd(
        cls,
        ref_usd: Decimal,
        config: Optional[PricingRuleConfig] = None
    ) -> Tuple[Decimal, Decimal]:
        """
        Calcula precio final en efectivo y precio final en tarjeta a partir
        de un valor de referencia en USD.
        """
        if config is None:
            config = cls.get_active_config()

        rate = config.usd_to_clp_rate
        base_clp = ref_usd * rate
        margin_multiplier = Decimal('1') + (config.commercial_margin_percent / Decimal('100'))
        price_with_margin = base_clp * margin_multiplier

        # Descuento en efectivo
        cash_multiplier = Decimal('1') - (config.cash_discount_percent / Decimal('100'))
        raw_cash = price_with_margin * cash_multiplier

        # Costo de procesamiento tarjeta
        card_multiplier = Decimal('1') + (config.card_processing_fee_percent / Decimal('100'))
        raw_card = price_with_margin * card_multiplier

        # Redondeo
        cash_price = cls.round_to_unit(raw_cash, config.rounding_unit)
        card_price = cls.round_to_unit(raw_card, config.rounding_unit)

        return cash_price, card_price

    @classmethod
    def calculate_prices_from_clp_cost(
        cls,
        cost_clp: Decimal,
        config: Optional[PricingRuleConfig] = None
    ) -> Tuple[Decimal, Decimal]:
        """
        Calcula precio de venta a partir del costo de adquisición interno en CLP.
        """
        if config is None:
            config = cls.get_active_config()

        margin_multiplier = Decimal('1') + (config.commercial_margin_percent / Decimal('100'))
        price_with_margin = cost_clp * margin_multiplier

        cash_multiplier = Decimal('1') - (config.cash_discount_percent / Decimal('100'))
        raw_cash = price_with_margin * cash_multiplier

        card_multiplier = Decimal('1') + (config.card_processing_fee_percent / Decimal('100'))
        raw_card = price_with_margin * card_multiplier

        cash_price = cls.round_to_unit(raw_cash, config.rounding_unit)
        card_price = cls.round_to_unit(raw_card, config.rounding_unit)

        return cash_price, card_price

    @classmethod
    @transaction.atomic
    def save_quote(
        cls,
        card_print: CardPrint,
        reference_price_usd: Optional[Decimal] = None,
        source: str = PriceQuote.Source.MANUAL,
        custom_cash_price: Optional[Decimal] = None,
        custom_card_price: Optional[Decimal] = None,
        config: Optional[PricingRuleConfig] = None
    ) -> PriceQuote:
        """
        Registra una cotización histórica, desactivando cotizaciones anteriores
        para garantizar una única cotización vigente (is_current=True).
        """
        if config is None:
            config = cls.get_active_config()

        # Desactivar cotizaciones anteriores
        PriceQuote.objects.filter(card_print=card_print, is_current=True).update(is_current=False)

        if custom_cash_price is not None and custom_card_price is not None:
            cash_price = custom_cash_price
            card_price = custom_card_price
        elif reference_price_usd is not None:
            cash_price, card_price = cls.calculate_prices_from_usd(reference_price_usd, config)
        else:
            # Si no hay USD ni precio manual, buscar costo promedio en inventario
            items = card_print.inventory_items.all()
            if items.exists():
                avg_cost = sum(i.acquisition_cost for i in items) / len(items)
                cash_price, card_price = cls.calculate_prices_from_clp_cost(avg_cost, config)
            else:
                cash_price = Decimal('1000.00')
                card_price = Decimal('1100.00')

        quote = PriceQuote.objects.create(
            card_print=card_print,
            source=source,
            reference_price_usd=reference_price_usd,
            usd_to_clp_rate_used=config.usd_to_clp_rate,
            calculated_cash_price=cash_price,
            calculated_card_price=card_price,
            is_current=True
        )
        return quote

    @classmethod
    @transaction.atomic
    def recalculate_all_quotes(cls, config: Optional[PricingRuleConfig] = None) -> int:
        """
        Recalcula todas las cotizaciones vigentes que tengan precio de referencia en USD.
        """
        if config is None:
            config = cls.get_active_config()

        current_quotes = list(PriceQuote.objects.filter(is_current=True, reference_price_usd__isnull=False))
        count = 0
        for q in current_quotes:
            cls.save_quote(
                card_print=q.card_print,
                reference_price_usd=q.reference_price_usd,
                source=q.source,
                config=config
            )
            count += 1
        return count
