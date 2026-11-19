import pytest
from apps.accounts.models import CustomUser

@pytest.mark.django_db
class TestAccounts:
    def test_create_admin_user(self):
        user = CustomUser.objects.create_user(
            username='admin_subarashii',
            email='admin@subarashii.cl',
            password='securepassword123',
            role=CustomUser.Role.ADMIN
        )
        assert user.is_store_admin is True
        assert user.is_store_seller is True
        assert str(user) == 'admin_subarashii (Administrador)'

    def test_create_seller_user(self):
        seller = CustomUser.objects.create_user(
            username='seller_caja1',
            email='caja1@subarashii.cl',
            password='securepassword123',
            role=CustomUser.Role.SELLER
        )
        assert seller.is_store_admin is False
        assert seller.is_store_seller is True
        assert str(seller) == 'seller_caja1 (Vendedor)'

    def test_create_customer_user(self):
        customer = CustomUser.objects.create_user(
            username='duelist_juan',
            email='juan@gmail.com',
            password='securepassword123',
            role=CustomUser.Role.CUSTOMER
        )
        assert customer.is_store_admin is False
        assert customer.is_store_seller is False
