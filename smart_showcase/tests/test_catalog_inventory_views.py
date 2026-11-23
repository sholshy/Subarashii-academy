import json
from unittest.mock import patch
import pytest
from datetime import date
from decimal import Decimal
from django.urls import reverse
from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.accounts.models import CustomUser
from apps.catalog.models import Card, CardPrint
from apps.inventory.models import InventoryItem
from integrations.base import CatalogCardData

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

    def test_catalog_card_create_view_get(self, client, admin_user):
        client.force_login(admin_user)
        url = reverse('catalog_card_create')
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Agregar Nueva Carta" in content
        assert "Importar desde YGOPRODeck / YGO Topdeck" in content
        assert "variantSelect" in content
        assert "Capturar Foto" in content

    def test_catalog_api_search_view(self, client, admin_user, sample_catalog_data):
        client.force_login(admin_user)
        url = reverse('catalog_api_search')
        
        # Test mock search
        mock_results = [CatalogCardData(
            ygoprodeck_id=46986414,
            name="Dark Magician",
            card_type="Normal Monster",
            description="The ultimate wizard in terms of attack and defence.",
            race="Spellcaster",
            attribute="DARK",
            atk=2500,
            def_points=2100,
            level=7,
            scale=None,
            link_val=None,
            archetype="Dark Magician",
            card_sets=[
                {
                    "set_name": "Legend of Blue Eyes White Dragon",
                    "set_code": "LOB-005",
                    "set_rarity": "Ultra Rare"
                }
            ],
            image_url="https://images.ygoprodeck.com/images/cards/46986414.jpg"
        )]
        
        with patch('apps.catalog.views.catalog_service.search_remote_cards', return_value=mock_results):
            response = client.get(f"{url}?q=Dark")
            assert response.status_code == 200
            data = json.loads(response.content)
            assert 'cards' in data
            assert len(data['cards']) == 1
            assert data['cards'][0]['name'] == "Dark Magician"
            assert len(data['cards'][0]['card_sets']) == 1

    def test_catalog_api_card_details_view(self, client, admin_user):
        client.force_login(admin_user)
        url = reverse('catalog_api_card_details', kwargs={'ygoprodeck_id': 46986414})
        
        mock_card_data = CatalogCardData(
            ygoprodeck_id=46986414,
            name="Dark Magician",
            card_type="Normal Monster",
            description="The ultimate wizard in terms of attack and defence.",
            race="Spellcaster",
            attribute="DARK",
            atk=2500,
            def_points=2100,
            level=7,
            scale=None,
            link_val=None,
            archetype="Dark Magician",
            card_sets=[
                {
                    "set_name": "Legend of Blue Eyes White Dragon",
                    "set_code": "LOB-005",
                    "set_rarity": "Ultra Rare",
                    "set_rarity_code": "UR"
                },
                {
                    "set_name": "Dark Beginning 1",
                    "set_code": "DB1-EN102",
                    "set_rarity": "Super Rare",
                    "set_rarity_code": "SR"
                }
            ],
            image_url="https://images.ygoprodeck.com/images/cards/46986414.jpg"
        )
        
        with patch('apps.catalog.views.catalog_service.provider.get_by_id', return_value=mock_card_data):
            response = client.get(url)
            assert response.status_code == 200
            data = json.loads(response.content)
            assert data['success'] is True
            assert data['card']['name'] == "Dark Magician"
            assert len(data['card']['card_sets']) == 2
            assert data['card']['card_sets'][0]['set_code'] == "LOB-005"
            assert data['card']['card_sets'][0]['set_rarity'] == "Ultra Rare"

    def test_catalog_card_create_with_image_and_inventory(self, client, admin_user):
        client.force_login(admin_user)
        url = reverse('catalog_card_create')

        # Dummy tiny 1x1 gif image
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff'
            b'\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00'
            b'\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
        )
        fake_image = SimpleUploadedFile("real_card.gif", small_gif, content_type="image/gif")

        post_data = {
            'name': 'Blue-Eyes White Dragon',
            'ygoprodeck_id': '89631139',
            'card_type': 'Normal Monster',
            'race': 'Dragon',
            'attribute': 'LIGHT',
            'print_code': 'LOB-001',
            'set_name': 'Legend of Blue Eyes White Dragon',
            'rarity': 'Ultra Rare',
            'edition': CardPrint.Edition.FIRST_EDITION,
            'language': CardPrint.Language.EN,
            'image_url': 'https://images.ygoprodeck.com/images/cards/89631139.jpg',
            'card_image': fake_image,
            'add_to_inventory': '1',
            'condition': InventoryItem.Condition.NEAR_MINT,
            'acquisition_cost': '75000',
            'location': 'Vitrina 1 - Espacio 4'
        }

        response = client.post(url, post_data)
        assert response.status_code == 302

        # Check Card and CardPrint created
        card = Card.objects.get(name='Blue-Eyes White Dragon')
        assert card.ygoprodeck_id == 89631139
        cprint = CardPrint.objects.get(card=card, print_code='LOB-001')
        assert cprint.rarity == 'Ultra Rare'
        assert cprint.edition == CardPrint.Edition.FIRST_EDITION
        assert cprint.language == CardPrint.Language.EN
        assert cprint.image.name != ""
        assert cprint.display_image_url == cprint.image.url

        # Check InventoryItem created
        item = InventoryItem.objects.get(print=cprint)
        assert item.condition == InventoryItem.Condition.NEAR_MINT
        assert item.acquisition_cost == Decimal('75000')
        assert item.location == 'Vitrina 1 - Espacio 4'

