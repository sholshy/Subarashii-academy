import pytest
from datetime import date
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from apps.catalog.models import Card, CardPrint
from apps.inventory.models import InventoryItem
from apps.showcases.models import Showcase, ShowcaseSlot, SlotAssignment

@pytest.mark.django_db
class TestShowcasesAndSlots:
    @pytest.fixture
    def setup_data(self):
        showcase = Showcase.objects.create(
            name="Vitrina Principal Yu-Gi-Oh!",
            code="VIT-01",
            total_rows=4,
            total_columns=4
        )
        slot1 = ShowcaseSlot.objects.create(
            showcase=showcase,
            slot_number=1,
            visible_code="VIT01-A01"
        )
        slot2 = ShowcaseSlot.objects.create(
            showcase=showcase,
            slot_number=2,
            visible_code="VIT01-A02"
        )

        card = Card.objects.create(name="Exodia the Forbidden One", ygoprodeck_id=33396948)
        card_print = CardPrint.objects.create(
            card=card,
            print_code="LOB-124",
            set_name="Legend of Blue Eyes",
            rarity="Ultra Rare",
            edition=CardPrint.Edition.FIRST_EDITION,
            language=CardPrint.Language.EN
        )

        item1 = InventoryItem.objects.create(
            print=card_print,
            condition=InventoryItem.Condition.NEAR_MINT,
            acquisition_cost=Decimal("50000.00"),
            acquisition_date=date.today(),
            status=InventoryItem.Status.IN_STOCK
        )
        item2 = InventoryItem.objects.create(
            print=card_print,
            condition=InventoryItem.Condition.LIGHTLY_PLAYED,
            acquisition_cost=Decimal("35000.00"),
            acquisition_date=date.today(),
            status=InventoryItem.Status.IN_STOCK
        )

        return {
            'showcase': showcase,
            'slot1': slot1,
            'slot2': slot2,
            'item1': item1,
            'item2': item2
        }

    def test_qr_token_permanence(self, setup_data):
        slot = setup_data['slot1']
        token = slot.qr_token
        assert token is not None
        assert slot.get_public_url().endswith(str(token))

    def test_assign_item_to_slot(self, setup_data):
        slot1 = setup_data['slot1']
        item1 = setup_data['item1']

        assignment = SlotAssignment.objects.create(
            slot=slot1,
            item=item1,
            is_active=True
        )

        assert slot1.current_assignment == assignment
        assert slot1.current_item == item1

    def test_prevent_two_active_cards_in_same_slot(self, setup_data):
        slot1 = setup_data['slot1']
        item1 = setup_data['item1']
        item2 = setup_data['item2']

        # First assignment succeeds
        SlotAssignment.objects.create(slot=slot1, item=item1, is_active=True)

        # Attempting second active assignment in same slot raises clean validation error or integrity error
        dup_assignment = SlotAssignment(slot=slot1, item=item2, is_active=True)
        with pytest.raises(ValidationError):
            dup_assignment.clean()

    def test_prevent_same_card_in_two_active_slots(self, setup_data):
        slot1 = setup_data['slot1']
        slot2 = setup_data['slot2']
        item1 = setup_data['item1']

        SlotAssignment.objects.create(slot=slot1, item=item1, is_active=True)

        dup_item_assignment = SlotAssignment(slot=slot2, item=item1, is_active=True)
        with pytest.raises(ValidationError):
            dup_item_assignment.clean()

    def test_unassign_workflow(self, setup_data):
        slot1 = setup_data['slot1']
        item1 = setup_data['item1']
        item1.status = InventoryItem.Status.IN_SHOWCASE
        item1.save()

        assignment = SlotAssignment.objects.create(slot=slot1, item=item1, is_active=True)
        assert slot1.current_item == item1

        # Unassign
        assignment.unassign(reason="Venta presencial o rotación")
        assignment.refresh_from_db()
        item1.refresh_from_db()

        assert assignment.is_active is False
        assert assignment.unassigned_at is not None
        assert slot1.current_item is None
        assert item1.status == InventoryItem.Status.IN_STOCK
