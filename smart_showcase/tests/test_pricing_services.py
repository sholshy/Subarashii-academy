import pytest
from decimal import Decimal
from apps.catalog.models import Card, CardPrint
from apps.pricing.models import PricingRuleConfig, PriceQuote
from apps.pricing.services import PricingService

@pytest.mark.django_db
class TestPricingServices:
    @pytest.fixture
    def pricing_config(self):
        return PricingRuleConfig.objects.create(
            name="Test Config",
            usd_to_clp_rate=Decimal("1000.00"),
            commercial_margin_percent=Decimal("20.00"),  # +20%
            cash_discount_percent=Decimal("10.00"),       # -10%
            card_processing_fee_percent=Decimal("5.00"), # +5%
            rounding_unit=100
        )

    @pytest.fixture
    def sample_print(self):
        card = Card.objects.create(name="Dark Magician Girl", ygoprodeck_id=38033121)
        return CardPrint.objects.create(
            card=card,
            print_code="MFC-000",
            set_name="Magician's Force",
            rarity="Secret Rare",
            edition=CardPrint.Edition.FIRST_EDITION,
            language=CardPrint.Language.EN
        )

    def test_calculate_prices_from_usd(self, pricing_config):
        # Ref USD: 10.00
        # Base CLP: 10 * 1000 = 10,000
        # Con Margen (+20%): 12,000
        # Efectivo (-10%): 12,000 * 0.90 = 10,800
        # Tarjeta (+5%): 12,000 * 1.05 = 12,600
        ref_usd = Decimal("10.00")
        cash, card = PricingService.calculate_prices_from_usd(ref_usd, pricing_config)

        assert cash == Decimal("10800")
        assert card == Decimal("12600")

    def test_save_quote_and_archive_previous(self, pricing_config, sample_print):
        # First quote
        q1 = PricingService.save_quote(
            card_print=sample_print,
            reference_price_usd=Decimal("20.00"),
            config=pricing_config
        )
        assert q1.is_current is True
        assert q1.calculated_cash_price == Decimal("21600")

        # Second quote with new USD value
        q2 = PricingService.save_quote(
            card_print=sample_print,
            reference_price_usd=Decimal("30.00"),
            config=pricing_config
        )
        assert q2.is_current is True
        q1.refresh_from_db()
        assert q1.is_current is False  # Previous archived

    def test_recalculate_all_quotes(self, pricing_config, sample_print):
        PricingService.save_quote(
            card_print=sample_print,
            reference_price_usd=Decimal("10.00"),
            config=pricing_config
        )

        # Update USD rate from 1000 to 1100
        pricing_config.usd_to_clp_rate = Decimal("1100.00")
        pricing_config.save()

        count = PricingService.recalculate_all_quotes(pricing_config)
        assert count == 1

        active_quote = PriceQuote.objects.get(card_print=sample_print, is_current=True)
        # Base: 10 * 1100 = 11,000. Margen +20% = 13,200. Efectivo -10% = 11,880 -> redondeo 100 = 11,900
        assert active_quote.calculated_cash_price == Decimal("11900")
