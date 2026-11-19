import pytest
from datetime import date
from decimal import Decimal
from django.urls import reverse
from django.test import Client
from apps.accounts.models import CustomUser
from apps.catalog.models import Card, CardPrint
from apps.inventory.models import InventoryItem

@pytest.mark.django_db
class TestCatalogInventoryViews:
    @pytest.fixture
    def client(self):
        return Client()

    @pytest.fixture
    def admin_user(self):
        return CustomUser.objects.create_user(
            username="admin_test",
            password="password123",
            role=CustomUser.Role.ADMIN
        )

    @pytest.fixture
    def sample_catalog_data(self):
        card = Card.objects.create(name="Dark Magician", ygoprodeck_id=46986414)
        cprint = CardPrint.objects.create(
            card=card,
            print_code="LOB-005",
            set_name="Legend of Blue Eyes",
            rarity="Ultra Rare",
            edition=CardPrint.Edition.FIRST_EDITION,
            language=CardPrint.Language.EN
        )
        return card, cprint

    def test_catalog_list_view(self, client, sample_catalog_data):
        url = reverse('catalog_list')
        response = client.get(url)
        assert response.status_code == 200
        assert "Dark Magician" in response.content.decode()

    def test_catalog_list_htmx_partial(self, client, sample_catalog_data):
        url = reverse('catalog_list')
        response = client.get(url, HTTP_HX_REQUEST='true')
        assert response.status_code == 200
        # Partial returns card_table without full html wrapper
        assert "<html" not in response.content.decode()
        assert "Dark Magician" in response.content.decode()

    def test_inventory_list_view_authenticated(self, client, admin_user, sample_catalog_data):
        _, cprint = sample_catalog_data
        InventoryItem.objects.create(
            print=cprint,
            condition=InventoryItem.Condition.NEAR_MINT,
            acquisition_cost=Decimal("15000.00"),
            acquisition_date=date.today(),
            status=InventoryItem.Status.IN_STOCK
        )

        client.force_login(admin_user)
        url = reverse('inventory_list')
        response = client.get(url)
        assert response.status_code == 200
        assert "Dark Magician" in response.content.decode()
        assert "15000" in response.content.decode()

    def test_inventory_create_view_post(self, client, admin_user, sample_catalog_data):
        _, cprint = sample_catalog_data
        client.force_login(admin_user)

        url = reverse('inventory_create')
        post_data = {
            'print_id': cprint.id,
            'condition': InventoryItem.Condition.NEAR_MINT,
            'acquisition_cost': '25000',
            'quantity': '2',
            'location': 'Vitrina Test',
            'notes': 'Test lote'
        }
        response = client.post(url, post_data)
        assert response.status_code == 302
        assert InventoryItem.objects.filter(print=cprint).count() == 2
