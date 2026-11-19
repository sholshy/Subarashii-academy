from django.db import models
from django.conf import settings

class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE = 'CREATE', 'Creación'
        UPDATE = 'UPDATE', 'Modificación'
        DELETE = 'DELETE', 'Eliminación'
        SLOT_ASSIGN = 'SLOT_ASSIGN', 'Asignación a Slot'
        SLOT_UNASSIGN = 'SLOT_UNASSIGN', 'Retiro de Slot'
        ORDER_STATUS = 'ORDER_STATUS', 'Cambio Estado Orden'
        PRICE_UPDATE = 'PRICE_UPDATE', 'Actualización de Precios'
        PAYMENT_CONFIRM = 'PAYMENT_CONFIRM', 'Confirmación de Pago'

    action = models.CharField(max_length=30, choices=Action.choices, db_index=True)
    model_name = models.CharField(max_length=100, db_index=True, verbose_name='Entidad / Modelo')
    object_id = models.CharField(max_length=100, db_index=True, verbose_name='ID del Objeto')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Usuario')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='Dirección IP')
    changes = models.JSONField(default=dict, blank=True, verbose_name='Detalle de Cambios')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Fecha y Hora')

    class Meta:
        verbose_name = 'Registro de Auditoría'
        verbose_name_plural = 'Registros de Auditoría'
        ordering = ['-created_at']

    def __str__(self) -> str:
        user_name = self.user.username if self.user else "Sistema"
        return f"[{self.created_at:%Y-%m-%d %H:%M:%S}] {user_name} -> {self.get_action_display()} en {self.model_name}:{self.object_id}"
