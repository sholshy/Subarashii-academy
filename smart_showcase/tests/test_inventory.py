import pytest
from datetime import date
from decimal import Decimal
from apps.catalog.models import Card, CardPrint
from apps.inventory.models import InventoryItem, InventoryMovement

@pytest.mark.django_db
class TestInventory:
    @pytest.fixture
    def sample_print(self):
        card = Card.objects.create(name="Red-Eyes Black Dragon", ygoprodeck_id=74677422)
        return CardPrint.objects.create(
            card=card,
            print_code="LOB-070",
            set_name="Legend of Blue Eyes White Dragon",
            rarity="Ultra Rare",
            edition=CardPrint.Edition.FIRST_EDITION,
            language=CardPrint.Language.EN
        )

    def test_create_inventory_item_auto_sku(self, sample_print):
        item = InventoryItem.objects.create(
            print=sample_print,
            condition=InventoryItem.Condition.NEAR_MINT,
            acquisition_cost=Decimal("15000.00"),
            acquisition_date=date.today(),
            status=InventoryItem.Status.IN_STOCK,
            location="Caja Principal"
        )
        assert item.sku.startswith("SUB-")
        assert item.status == InventoryItem.Status.IN_STOCK
        assert "LOB-070" in str(item)

    def test_inventory_movement_logging(self, sample_print):
        item = InventoryItem.objects.create(
            print=sample_print,
            condition=InventoryItem.Condition.NEAR_MINT,
            acquisition_cost=Decimal("20000.00"),
            acquisition_date=date.today(),
            status=InventoryItem.Status.IN_STOCK,
            location="Bodega"
        )

        # Log movement
        movement = InventoryMovement.objects.create(
            item=item,
            from_status=InventoryItem.Status.IN_STOCK,
            to_status=InventoryItem.Status.IN_SHOWCASE,
            from_location="Bodega",
            to_location="Vitrina 1 - Slot A01",
            reason="Montaje de vitrina temática"
        )
        assert movement.pk is not None
        assert item.movements.count() == 1
