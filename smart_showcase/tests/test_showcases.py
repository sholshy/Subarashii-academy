import pytest
from datetime import date
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse
from apps.accounts.models import CustomUser
from apps.catalog.models import Card, CardPrint
from apps.inventory.models import InventoryItem
from apps.pricing.models import PriceQuote, PricingRuleConfig
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

    @pytest.fixture
    def admin_user(self):
        from apps.accounts.models import CustomUser
        return CustomUser.objects.create_user(
            username="admin_test",
            email="admin@test.cl",
            password="pass",
            role=CustomUser.Role.ADMIN,
            is_staff=True,
            is_superuser=True
        )

    def test_showcase_edit_view_post_updates_capacity(self, client, admin_user, setup_data):
        """Verifica que el endpoint de edición de vitrina actualice filas, columnas y capacidad correctamente."""
        client.force_login(admin_user)
        showcase = setup_data['showcase']
        response = client.post(f"/showcases/{showcase.id}/edit/", {
            'name': 'Vitrina Editada',
            'contact_whatsapp': '+56999887766',
            'description': 'Nueva descripción',
            'total_rows': '3',
            'total_columns': '6',
            'is_active': '1'
        }, follow=True)

        assert response.status_code == 200
        showcase.refresh_from_db()
        assert showcase.name == 'Vitrina Editada'
        assert showcase.total_rows == 3
        assert showcase.total_columns == 6
        assert showcase.capacity == 18
        assert showcase.slots.filter(is_active=True).count() == 18

    def test_showcase_edit_view_post_total_spaces_preset(self, client, admin_user, setup_data):
        """Verifica que enviar total_spaces directamente calcule dimensiones y ajuste la capacidad."""
        client.force_login(admin_user)
        showcase = setup_data['showcase']
        response = client.post(f"/showcases/{showcase.id}/edit/", {
            'name': 'Vitrina 20 Espacios',
            'total_spaces': '20',
            'total_rows': '4',
            'total_columns': '4',
            'is_active': '1'
        }, follow=True)

        assert response.status_code == 200
        showcase.refresh_from_db()
        assert showcase.total_rows == 4
        assert showcase.total_columns == 5
        assert showcase.capacity == 20
        assert showcase.slots.filter(is_active=True).count() == 20

    def test_showcase_quick_intake_view_get(self, client, admin_user, setup_data):
        client.force_login(admin_user)
        slot1 = setup_data['slot1']
        url = reverse('showcase_quick_intake')
        response = client.get(f"{url}?slot_id={slot1.id}")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Ingresar Carta a Vitrina" in content
        assert "variantSelect" in content
        assert "refUsdInput" in content
        assert slot1.visible_code in content

    def test_showcase_quick_intake_view_post_creates_and_assigns(self, client, admin_user, setup_data):
        client.force_login(admin_user)
        slot2 = setup_data['slot2']
        url = reverse('showcase_quick_intake')

        post_data = {
            'name': 'Red-Eyes Black Dragon',
            'ygoprodeck_id': '74677422',
            'card_type': 'Normal Monster',
            'race': 'Dragon',
            'attribute': 'DARK',
            'atk': '2400',
            'def_points': '2000',
            'level': '7',
            'print_code': 'LOB-070',
            'set_name': 'Legend of Blue Eyes White Dragon',
            'rarity': 'Ultra Rare',
            'edition': '1ST',
            'language': 'EN',
            'ref_usd': '25.00',
            'cash_price': '28000',
            'card_price': '30000',
            'condition': 'NM',
            'owner_name': 'Carlos Consignatario',
            'owner_phone': '+56987654321',
            'owner_rut': '18.765.432-1',
            'owner_bank': 'Banco de Chile',
            'owner_account_type': 'Cuenta Corriente',
            'owner_account_number': '0012345678',
            'owner_email': 'carlos@consignatario.cl',
            'owner_payout_amount': '22000',
            'slot_id': slot2.id,
        }

        response = client.post(url, post_data)
        assert response.status_code == 302
        assert response.url == reverse('public_slot_detail', kwargs={'qr_token': slot2.qr_token})

        # Verificar carta y print
        card = Card.objects.get(name='Red-Eyes Black Dragon')
        cprint = CardPrint.objects.get(card=card, print_code='LOB-070')
        assert cprint.rarity == 'Ultra Rare'

        # Verificar cotización
        quote = PriceQuote.objects.get(card_print=cprint, is_current=True)
        assert quote.calculated_cash_price == Decimal('28000')

        # Verificar item físico de inventario con dueño y datos bancarios
        item = InventoryItem.objects.get(print=cprint)
        assert item.owner_name == 'Carlos Consignatario'
        assert item.owner_bank == 'Banco de Chile'
        assert item.owner_account_number == '0012345678'
        assert item.owner_payout_amount == Decimal('22000')
        assert item.status == InventoryItem.Status.IN_SHOWCASE

        # Verificar asignación a slot
        assert slot2.current_item == item

    def test_public_slot_detail_admin_vs_public(self, client, admin_user, setup_data):
        slot1 = setup_data['slot1']
        item1 = setup_data['item1']
        item1.owner_name = "Pedro Dueño"
        item1.owner_bank = "Banco Estado"
        item1.owner_account_number = "98765432"
        item1.owner_rut = "15.432.109-8"
        item1.owner_payout_amount = Decimal("40000")
        item1.save()

        # Asignar item1 a slot1
        SlotAssignment.objects.create(slot=slot1, item=item1, is_active=True)

        url = reverse('public_slot_detail', kwargs={'qr_token': slot1.qr_token})

        # 1. Acceso público (anónimo)
        response_anon = client.get(url)
        assert response_anon.status_code == 200
        content_anon = response_anon.content.decode()
        assert "Exodia the Forbidden One" in content_anon
        assert "Efectivo" in content_anon
        assert "Consultar / Reservar por WhatsApp" in content_anon
        # Datos del dueño NO deben aparecer para público
        assert "Panel Admin: Propietario" not in content_anon
        assert "Pedro Dueño" not in content_anon
        assert "Banco Estado" not in content_anon
        assert "98765432" not in content_anon

        # 2. Acceso como Admin logueado
        client.force_login(admin_user)
        response_admin = client.get(url)
        assert response_admin.status_code == 200
        content_admin = response_admin.content.decode()
        assert "Panel Admin: Propietario y Liquidación" in content_admin
        assert "Pedro Dueño" in content_admin
        assert "Banco Estado" in content_admin
        assert "98765432" in content_admin
        assert "Copiar Datos" in content_admin

    def test_showcase_delete_view_with_active_and_historical_assignments(self, client, admin_user, setup_data):
        client.force_login(admin_user)
        showcase = setup_data['showcase']
        slot1 = setup_data['slot1']
        slot2 = setup_data['slot2']
        item1 = setup_data['item1']
        item2 = setup_data['item2']

        # Crear asignación activa en slot1
        SlotAssignment.objects.create(slot=slot1, item=item1, is_active=True)
        # Crear asignación histórica (inactiva / finalizada) en slot2
        SlotAssignment.objects.create(slot=slot2, item=item2, is_active=False)

        delete_url = reverse('showcase_delete', kwargs={'showcase_id': showcase.id})
        response = client.post(delete_url, follow=True)
        assert response.status_code == 200

        # Verificar que la vitrina fue eliminada sin ProtectedError
        assert not Showcase.objects.filter(id=showcase.id).exists()
        assert not ShowcaseSlot.objects.filter(showcase_id=showcase.id).exists()

        # Verificar que la carta activa regresó a bodega
        item1.refresh_from_db()
        assert item1.status == InventoryItem.Status.IN_STOCK


