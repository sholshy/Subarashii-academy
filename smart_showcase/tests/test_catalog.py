import pytest
from django.db import IntegrityError
from apps.catalog.models import Card, CardPrint

@pytest.mark.django_db
class TestCatalog:
    def test_create_card_and_auto_clean_name(self):
        card = Card.objects.create(
            name="Blue-Eyes White Dragon",
            ygoprodeck_id=89631139,
            card_type="Normal Monster",
            atk=3000,
            def_points=2500,
            level=8,
            attribute="LIGHT",
            race="Dragon"
        )
        assert card.clean_name == "blue-eyes-white-dragon"
        assert str(card) == "Blue-Eyes White Dragon"

    def test_card_print_creation_and_uniqueness(self):
        card = Card.objects.create(name="Dark Magician", ygoprodeck_id=46986414)
        
        print1 = CardPrint.objects.create(
            card=card,
            print_code="LOB-005",
            set_name="Legend of Blue Eyes White Dragon",
            rarity="Ultra Rare",
            rarity_code="UR",
            edition=CardPrint.Edition.FIRST_EDITION,
            language=CardPrint.Language.EN
        )
        assert print1.pk is not None
        assert "LOB-005" in str(print1)

        # Duplicate print with same code, rarity, edition and language must fail
        with pytest.raises(IntegrityError):
            CardPrint.objects.create(
                card=card,
                print_code="LOB-005",
                set_name="Legend of Blue Eyes White Dragon",
                rarity="Ultra Rare",
                rarity_code="UR",
                edition=CardPrint.Edition.FIRST_EDITION,
                language=CardPrint.Language.EN
            )
