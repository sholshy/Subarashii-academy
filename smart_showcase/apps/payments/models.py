import uuid
from django.db import models
from apps.sales.models import Order

class PaymentAttempt(models.Model):
    class Provider(models.TextChoices):
        TUU_CHECKOUT = 'TUU_CHECKOUT', 'TUU Pago Online'
        TUU_POS = 'TUU_POS', 'Terminal POS TUU'
        CASH = 'CASH', 'Caja Efectivo'

    class Status(models.TextChoices):
        INITIATED = 'INITIATED', 'Iniciado'
        SUCCESS = 'SUCCESS', 'Aprobado / Pagado'
        FAILED = 'FAILED', 'Rechazado'
        CANCELLED = 'CANCELLED', 'Cancelado'

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payment_attempts', verbose_name='Orden')
    provider = models.CharField(max_length=30, choices=Provider.choices, default=Provider.TUU_CHECKOUT)
    external_transaction_id = models.CharField(max_length=120, blank=True, db_index=True, verbose_name='ID Transacción Externa')
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INITIATED, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Monto Cobrado (CLP)')
    signature_verified = models.BooleanField(default=False, verbose_name='Firma Criptográfica Verificada')
    raw_response = models.JSONField(default=dict, blank=True, verbose_name='Respuesta Cruda de Pasarela')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Intento de Pago'
        verbose_name_plural = 'Intentos de Pago'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.order.order_number} - {self.provider} [{self.get_status_display()}] (${self.amount:,.0f})"


class WebhookLog(models.Model):
    provider = models.CharField(max_length=50, default='TUU')
    event_type = models.CharField(max_length=100, blank=True)
    signature = models.CharField(max_length=255, blank=True)
    is_valid = models.BooleanField(default=False)
    processed = models.BooleanField(default=False)
    payload = models.JSONField(default=dict)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Log de Webhook'
        verbose_name_plural = 'Logs de Webhooks'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"Webhook {self.provider} ({self.created_at:%Y-%m-%d %H:%M:%S}) - Válido: {self.is_valid}"
