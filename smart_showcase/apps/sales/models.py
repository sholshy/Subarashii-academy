import uuid
from django.db import models
from django.conf import settings
from apps.inventory.models import InventoryItem

class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pendiente'
        PAYMENT_PROCESSING = 'PAYMENT_PROCESSING', 'Pago en Proceso'
        PAID = 'PAID', 'Pagada'
        CANCELLED = 'CANCELLED', 'Cancelada'
        EXPIRED = 'EXPIRED', 'Expirada'
        REFUNDED = 'REFUNDED', 'Reembolsada'
        FAILED = 'FAILED', 'Fallida'

    class PaymentType(models.TextChoices):
        ONLINE_TUU = 'ONLINE_TUU', 'TUU Online (WebPay / Débito / Crédito)'
        POS_TUU = 'POS_TUU', 'Terminal POS TUU (Presencial)'
        CASH = 'CASH', 'Efectivo en Caja'

    order_number = models.CharField(
        max_length=40,
        unique=True,
        db_index=True,
        verbose_name='Número de Orden'
    )
    status = models.CharField(
        max_length=25,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name='Estado de la Orden'
    )
    payment_type = models.CharField(
        max_length=20,
        choices=PaymentType.choices,
        default=PaymentType.ONLINE_TUU,
        verbose_name='Forma de Pago'
    )
    customer_name = models.CharField(max_length=150, blank=True, verbose_name='Nombre Cliente')
    customer_email = models.EmailField(blank=True, verbose_name='Email Cliente')
    customer_phone = models.CharField(max_length=30, blank=True, verbose_name='Teléfono')
    
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Monto Total (CLP)'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Orden de Venta'
        verbose_name_plural = 'Órdenes de Venta'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = f"ORD-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.order_number} - ${self.total_amount:,.0f} [{self.get_status_display()}]"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name='Orden')
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name='order_items', verbose_name='Ejemplar Físico')
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Precio de Venta (CLP)')

    class Meta:
        verbose_name = 'Item de Orden'
        verbose_name_plural = 'Items de Órdenes'

    def __str__(self) -> str:
        return f"{self.order.order_number} -> {self.item.sku} (${self.unit_price:,.0f})"


class InventoryReservation(models.Model):
    item = models.OneToOneField(InventoryItem, on_delete=models.CASCADE, related_name='active_reservation', verbose_name='Carta Física')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='reservations', verbose_name='Orden Asociada')
    expires_at = models.DateTimeField(db_index=True, verbose_name='Expira en')
    is_active = models.BooleanField(default=True, db_index=True, verbose_name='Reserva Vigente')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Reserva de Inventario'
        verbose_name_plural = 'Reservas de Inventario'

    def __str__(self) -> str:
        return f"Reserva {self.item.sku} para {self.order.order_number} (Expira: {self.expires_at:%H:%M:%S})"
