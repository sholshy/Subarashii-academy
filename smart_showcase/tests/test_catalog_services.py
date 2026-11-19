import pytest
from apps.catalog.models import Card, CardPrint
from apps.catalog.services import CatalogService
from integrations.base import BaseCatalogProvider, CatalogCardData

class MockCatalogProvider(BaseCatalogProvider):
    def __init__(self):
        self.mock_data = CatalogCardData(
            ygoprodeck_id=46986414,
            name="Dark Magician",
            card_type="Normal Monster",
            description="The ultimate wizard in terms of attack and defense.",
            race="Spellcaster",
            attribute="DARK",
            atk=2500,
            def_points=2100,
            level=7,
            scale=None,
            link_val=None,
            archetype="Dark Magician",
            card_sets=[
                {"set_name": "Legend of Blue Eyes White Dragon", "set_code": "LOB-005", "set_rarity": "Ultra Rare", "set_rarity_code": "UR", "set_edition": "1st Edition"},
                {"set_name": "Starter Deck Yugi", "set_code": "SDY-006", "set_rarity": "Ultra Rare", "set_rarity_code": "UR", "set_edition": "Unlimited"}
            ],
            image_url="https://images.ygoprodeck.com/images/cards/46986414.jpg"
        )

    def search_by_name(self, name: str):
        if "Dark" in name or "Magician" in name:
            return [self.mock_data]
        return []

    def get_by_id(self, card_id: int):
        if card_id == 46986414:
            return self.mock_data
        return None

    def search_by_set_code(self, set_code: str):
        return [self.mock_data]

@pytest.mark.django_db
class TestCatalogServices:
    @pytest.fixture
    def service(self):
        return CatalogService(provider=MockCatalogProvider())

    def test_import_from_ygoprodeck_data(self, service):
        data = service.provider.get_by_id(46986414)
        card, prints_count = service.import_card_from_ygoprodeck_data(data)

        assert card.name == "Dark Magician"
        assert card.clean_name == "dark-magician"
        assert card.ygoprodeck_id == 46986414
        assert prints_count == 2
        assert card.prints.count() == 2

        # Check print attributes
        lob_print = card.prints.get(print_code="LOB-005")
        assert lob_print.rarity == "Ultra Rare"
        assert lob_print.edition == CardPrint.Edition.FIRST_EDITION
        assert lob_print.language == CardPrint.Language.EN
        assert lob_print.image_url == "https://images.ygoprodeck.com/images/cards/46986414.jpg"

    def test_import_idempotency(self, service):
        data = service.provider.get_by_id(46986414)
        # First import
        service.import_card_from_ygoprodeck_data(data)
        assert Card.objects.filter(ygoprodeck_id=46986414).count() == 1
        assert CardPrint.objects.filter(card__ygoprodeck_id=46986414).count() == 2

        # Second import with same data must NOT duplicate cards or prints
        card, new_prints = service.import_card_from_ygoprodeck_data(data)
        assert new_prints == 0
        assert Card.objects.filter(ygoprodeck_id=46986414).count() == 1
        assert CardPrint.objects.filter(card__ygoprodeck_id=46986414).count() == 2

    def test_create_custom_card_and_print(self, service):
        card = service.create_custom_card(
            name="Slifer the Sky Dragon (Custom)",
            card_type="Divine-Beast / Effect",
            atk=None,
            def_points=None,
            level=10,
            attribute="DIVINE"
        )
        assert card.pk is not None
        assert card.clean_name == "slifer-the-sky-dragon-custom"

        cprint = service.create_custom_print(
            card=card,
            print_code="CUSTOM-001",
            set_name="Torneo Especial Subarashii",
            rarity="Secret Rare",
            edition=CardPrint.Edition.LIMITED,
            language=CardPrint.Language.ES
        )
        assert cprint.pk is not None
        assert cprint.edition == CardPrint.Edition.LIMITED
        assert cprint.language == CardPrint.Language.ES
