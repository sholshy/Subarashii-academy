import pytest
from decimal import Decimal
from datetime import date
from apps.accounts.models import CustomUser
from apps.catalog.models import Card, CardPrint
from apps.inventory.models import InventoryItem, InventoryMovement
from apps.inventory.services import InventoryService

@pytest.mark.django_db
class TestInventoryServices:
    @pytest.fixture
    def test_user(self):
        return CustomUser.objects.create_user(
            username="seller_ana",
            email="ana@subarashii.cl",
            password="testpassword",
            role=CustomUser.Role.SELLER
        )

    @pytest.fixture
    def sample_print(self):
        card = Card.objects.create(name="Pot of Greed", ygoprodeck_id=55144522)
        return CardPrint.objects.create(
            card=card,
            print_code="LOB-119",
            set_name="Legend of Blue Eyes White Dragon",
            rarity="Super Rare",
            edition=CardPrint.Edition.FIRST_EDITION,
            language=CardPrint.Language.EN
        )

    def test_create_item_with_movement(self, test_user, sample_print):
        item = InventoryService.create_item(
            card_print=sample_print,
            condition=InventoryItem.Condition.NEAR_MINT,
            acquisition_cost=Decimal("12000.00"),
            location="Caja A1",
            notes="Comprada en tienda",
            user=test_user
        )

        assert item.pk is not None
        assert item.sku.startswith("SUB-")
        assert item.status == InventoryItem.Status.IN_STOCK
        assert item.acquisition_cost == Decimal("12000.00")

        # Movement tracking
        movements = item.movements.all()
        assert movements.count() == 1
        m = movements.first()
        assert m.to_status == InventoryItem.Status.IN_STOCK
        assert m.to_location == "Caja A1"
        assert m.user == test_user

    def test_bulk_create_items(self, test_user, sample_print):
        items = InventoryService.bulk_create_items(
            card_print=sample_print,
            quantity=3,
            condition=InventoryItem.Condition.LIGHTLY_PLAYED,
            acquisition_cost=Decimal("8000.00"),
            user=test_user
        )

        assert len(items) == 3
        skus = [i.sku for i in items]
        assert len(set(skus)) == 3  # All SKUs must be unique
        for item in items:
            assert item.movements.count() == 1

    def test_update_item_status(self, test_user, sample_print):
        item = InventoryService.create_item(
            card_print=sample_print,
            condition=InventoryItem.Condition.NEAR_MINT,
            acquisition_cost=Decimal("10000.00"),
            location="Bodega",
            user=test_user
        )

        # Update status to IN_SHOWCASE
        updated = InventoryService.update_item_status(
            item=item,
            new_status=InventoryItem.Status.IN_SHOWCASE,
            new_location="Vitrina 1 - Slot 01",
            user=test_user,
            reason="Montaje de vitrina"
        )

        assert updated.status == InventoryItem.Status.IN_SHOWCASE
        assert updated.location == "Vitrina 1 - Slot 01"
        assert item.movements.count() == 2

        last_movement = item.movements.first()
        assert last_movement.from_status == InventoryItem.Status.IN_STOCK
        assert last_movement.to_status == InventoryItem.Status.IN_SHOWCASE
        assert last_movement.reason == "Montaje de vitrina"
