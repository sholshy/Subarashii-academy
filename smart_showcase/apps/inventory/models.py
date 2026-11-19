import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.catalog.models import CardPrint

class InventoryItem(models.Model):
    class Condition(models.TextChoices):
        NEAR_MINT = 'NM', 'Near Mint'
        LIGHTLY_PLAYED = 'LP', 'Lightly Played'
        MODERATELY_PLAYED = 'MP', 'Moderately Played'
        HEAVILY_PLAYED = 'HP', 'Heavily Played'
        DAMAGED = 'DMG', 'Damaged'

    class Status(models.TextChoices):
        IN_STOCK = 'IN_STOCK', 'En Bodega / Almacén'
        IN_SHOWCASE = 'IN_SHOWCASE', 'En Vitrina'
        RESERVED = 'RESERVED', 'Reservada Temporalmente'
        SOLD = 'SOLD', 'Vendida'
        RETURNED = 'RETURNED', 'Devuelta'
        DAMAGED = 'DAMAGED', 'Dañada'
        LOST = 'LOST', 'Extraviada'

    sku = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        verbose_name='SKU / Código Único',
        help_text='Identificador único del ejemplar físico.'
    )
    print = models.ForeignKey(
        CardPrint,
        on_delete=models.PROTECT,
        related_name='inventory_items',
        verbose_name='Impresión de Carta'
    )
    condition = models.CharField(
        max_length=10,
        choices=Condition.choices,
        default=Condition.NEAR_MINT,
        verbose_name='Condición Física'
    )
    acquisition_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Costo de Adquisición (CLP)'
    )
    acquisition_date = models.DateField(
        default=timezone.now,
        verbose_name='Fecha de Ingreso'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IN_STOCK,
        db_index=True,
        verbose_name='Estado'
    )
    location = models.CharField(
        max_length=120,
        blank=True,
        verbose_name='Ubicación Física'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='Notas Internas'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Carta Física (Inventario)'
        verbose_name_plural = 'Cartas Físicas (Inventario)'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.sku:
            # Generate deterministic/readable default SKU if omitted
            self.sku = f"SUB-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"[{self.sku}] {self.print.card.name} ({self.print.print_code}) - {self.get_condition_display()} [{self.get_status_display()}]"


class InventoryMovement(models.Model):
    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name='movements',
        verbose_name='Item de Inventario'
    )
    from_status = models.CharField(max_length=20, verbose_name='Estado Anterior')
    to_status = models.CharField(max_length=20, verbose_name='Nuevo Estado')
    from_location = models.CharField(max_length=120, blank=True, verbose_name='Ubicación Anterior')
    to_location = models.CharField(max_length=120, blank=True, verbose_name='Nueva Ubicación')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Usuario Responsable'
    )
    reason = models.CharField(max_length=255, blank=True, verbose_name='Motivo / Referencia')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha y Hora')

    class Meta:
        verbose_name = 'Movimiento de Inventario'
        verbose_name_plural = 'Movimientos de Inventario'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"Movimiento {self.item.sku}: {self.from_status} -> {self.to_status} ({self.created_at:%Y-%m-%d %H:%M})"
