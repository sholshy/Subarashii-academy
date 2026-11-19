import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from apps.accounts.models import CustomUser
from apps.catalog.models import Card, CardPrint
from apps.inventory.models import InventoryItem
from apps.showcases.models import Showcase, ShowcaseSlot, SlotAssignment
from apps.showcases.services import ShowcaseService

@pytest.mark.django_db
class TestShowcaseServices:
    @pytest.fixture
    def seller_user(self):
        return CustomUser.objects.create_user(
            username="seller_marcos",
            email="marcos@subarashii.cl",
            password="pass",
            role=CustomUser.Role.SELLER
        )

    @pytest.fixture
    def sample_item(self):
        card = Card.objects.create(name="Stardust Dragon", ygoprodeck_id=44508094)
        cprint = CardPrint.objects.create(
            card=card,
            print_code="TDGS-EN040",
            set_name="The Duelist Genesis",
            rarity="Ultra Rare",
            edition=CardPrint.Edition.FIRST_EDITION,
            language=CardPrint.Language.EN
        )
        return InventoryItem.objects.create(
            print=cprint,
            condition=InventoryItem.Condition.NEAR_MINT,
            acquisition_cost=Decimal("30000.00"),
            status=InventoryItem.Status.IN_STOCK
        )

    def test_create_showcase_with_auto_slots(self):
        showcase, count = ShowcaseService.create_showcase(
            name="Vitrina Principal",
            code="VIT-PRIN",
            total_rows=3,
            total_columns=4
        )
        assert count == 12
        assert showcase.slots.count() == 12

        # Check naming convention: Fila A -> A01, A02, A03, A04; Fila B -> B01...
        first_slot = showcase.slots.first()
        assert first_slot.visible_code == "VIT-PRIN-A01"
        assert first_slot.qr_token is not None

        last_slot = showcase.slots.last()
        assert last_slot.visible_code == "VIT-PRIN-C04"

    def test_assign_and_unassign_workflow(self, seller_user, sample_item):
        showcase, _ = ShowcaseService.create_showcase(
            name="Vitrina Test",
            code="VT-01",
            total_rows=2,
            total_columns=2
        )
        slot = showcase.slots.first()
        original_qr_token = slot.qr_token

        # 1. Asignar
        assignment = ShowcaseService.assign_item_to_slot(
            slot=slot,
            item=sample_item,
            user=seller_user,
            notes="Fila superior"
        )
        assert assignment.is_active is True
        assert slot.current_item == sample_item

        sample_item.refresh_from_db()
        assert sample_item.status == InventoryItem.Status.IN_SHOWCASE
        assert "Slot VT-01-A01" in sample_item.location

        # 2. Retirar
        unassigned_item = ShowcaseService.unassign_slot(slot=slot, user=seller_user, reason="Venta presencial")
        assert unassigned_item == sample_item
        assert slot.current_item is None

        sample_item.refresh_from_db()
        assert sample_item.status == InventoryItem.Status.IN_STOCK

        # 3. El QR token del slot debe permanecer IDÉNTICO
        slot.refresh_from_db()
        assert slot.qr_token == original_qr_token

    def test_prevent_double_assignment(self, seller_user, sample_item):
        showcase, _ = ShowcaseService.create_showcase(name="Vitrina", code="V-DUB", total_rows=1, total_columns=2)
        slot1 = showcase.slots.first()
        slot2 = showcase.slots.last()

        ShowcaseService.assign_item_to_slot(slot=slot1, item=sample_item, user=seller_user)

        # Intento de asignar el mismo ítem a otro slot debe fallar
        with pytest.raises(ValidationError):
            ShowcaseService.assign_item_to_slot(slot=slot2, item=sample_item, user=seller_user)

    def test_get_showcase_matrix(self, sample_item):
        showcase, _ = ShowcaseService.create_showcase(name="Vitrina M", code="VM", total_rows=2, total_columns=3)
        matrix = ShowcaseService.get_showcase_matrix(showcase)
        assert len(matrix) == 2
        assert len(matrix[0]['slots']) == 3
        assert matrix[0]['row_letter'] == 'A'
        assert matrix[1]['row_letter'] == 'B'
