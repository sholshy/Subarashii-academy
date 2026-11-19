import pytest
from decimal import Decimal
from django.test import Client
from django.urls import reverse
from apps.catalog.models import Card, CardPrint
from apps.inventory.models import InventoryItem
from apps.showcases.models import Showcase, ShowcaseSlot, SlotAssignment
from apps.pricing.models import PriceQuote

@pytest.mark.django_db
class TestPublicStorefront:
    @pytest.fixture
    def client(self):
        return Client()

    @pytest.fixture
    def setup_data(self):
        showcase = Showcase.objects.create(name="Vitrina Principal", code="VIT-01")
        slot_empty = ShowcaseSlot.objects.create(showcase=showcase, slot_number=1, visible_code="VIT01-A01")
        slot_occupied = ShowcaseSlot.objects.create(showcase=showcase, slot_number=2, visible_code="VIT01-A02")

        card = Card.objects.create(name="Cyber Dragon", ygoprodeck_id=70095154)
        cprint = CardPrint.objects.create(
            card=card,
            print_code="CRV-EN015",
            set_name="Cybernetic Revolution",
            rarity="Ultra Rare",
            edition=CardPrint.Edition.FIRST_EDITION,
            language=CardPrint.Language.EN
        )
        item = InventoryItem.objects.create(
            print=cprint,
            condition=InventoryItem.Condition.NEAR_MINT,
            acquisition_cost=Decimal("18000.00"),
            status=InventoryItem.Status.IN_SHOWCASE
        )

        SlotAssignment.objects.create(slot=slot_occupied, item=item, is_active=True)

        PriceQuote.objects.create(
            card_print=cprint,
            source=PriceQuote.Source.MANUAL,
            calculated_cash_price=Decimal("22000.00"),
            calculated_card_price=Decimal("24000.00"),
            is_current=True
        )

        return {
            'slot_empty': slot_empty,
            'slot_occupied': slot_occupied,
            'item': item,
            'card': card
        }

    def test_public_showcase_index_redirects(self, client):
        url = reverse('public_showcase_index')
        response = client.get(url)
        assert response.status_code == 302
        assert response.url == reverse('showcase_list')

    def test_public_slot_detail_empty(self, client, setup_data):
        slot = setup_data['slot_empty']
        url = reverse('public_slot_detail', kwargs={'qr_token': slot.qr_token})
        
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Espacio Disponible" in content
        assert slot.visible_code in content

    def test_public_slot_detail_occupied(self, client, setup_data):
        slot = setup_data['slot_occupied']
        item = setup_data['item']
        url = reverse('public_slot_detail', kwargs={'qr_token': slot.qr_token})

        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()

        # Visible public card info
        assert "Cyber Dragon" in content
        assert "CRV-EN015" in content
        assert "Near Mint" in content
        assert "22.000" in content or "22000" in content
        assert "24.000" in content or "24000" in content
        assert "Disponible en Vitrina" in content

        # CRITICAL SECURITY CHECK: Never expose internal acquisition cost
        assert str(item.acquisition_cost) not in content
        assert "Costo de Adquisición" not in content

    def test_public_slot_inactive_raises_404(self, client, setup_data):
        slot = setup_data['slot_empty']
        slot.is_active = False
        slot.save()

        url = reverse('public_slot_detail', kwargs={'qr_token': slot.qr_token})
        response = client.get(url)
        assert response.status_code == 404
