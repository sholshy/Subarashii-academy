from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Administrador'
        SELLER = 'SELLER', 'Vendedor'
        CUSTOMER = 'CUSTOMER', 'Cliente'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CUSTOMER,
        verbose_name='Rol'
    )
    phone_number = models.CharField(
        max_length=30,
        blank=True,
        verbose_name='Número de Teléfono'
    )

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    @property
    def is_store_admin(self) -> bool:
        return self.is_superuser or self.role == self.Role.ADMIN

    @property
    def is_store_seller(self) -> bool:
        return self.is_store_admin or self.role == self.Role.SELLER

    def __str__(self) -> str:
        return f"{self.username} ({self.get_role_display()})"
