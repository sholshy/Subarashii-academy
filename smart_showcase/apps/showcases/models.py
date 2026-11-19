import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.inventory.models import InventoryItem

class Showcase(models.Model):
    name = models.CharField(max_length=150, verbose_name='Nombre de la Vitrina')
    code = models.CharField(max_length=30, unique=True, db_index=True, verbose_name='Código de Vitrina')
    description = models.TextField(blank=True, verbose_name='Descripción / Ubicación en Tienda')
    total_rows = models.PositiveIntegerField(default=4, verbose_name='Total de Filas')
    total_columns = models.PositiveIntegerField(default=8, verbose_name='Total de Columnas')
    is_active = models.BooleanField(default=True, verbose_name='Activa')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Vitrina'
        verbose_name_plural = 'Vitrinas'
        ordering = ['code']

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"

    @property
    def capacity(self) -> int:
        return self.total_rows * self.total_columns


class ShowcaseSlot(models.Model):
    showcase = models.ForeignKey(
        Showcase,
        on_delete=models.CASCADE,
        related_name='slots',
        verbose_name='Vitrina'
    )
    slot_number = models.PositiveIntegerField(
        verbose_name='Número de Slot'
    )
    visible_code = models.CharField(
        max_length=40,
        db_index=True,
        verbose_name='Código Visible',
        help_text='Código impreso legible en la vitrina física (ej. V1-A01).'
    )
    qr_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Token QR Único Permanente'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Activo'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Espacio de Vitrina (Slot)'
        verbose_name_plural = 'Espacios de Vitrina (Slots)'
        constraints = [
            models.UniqueConstraint(fields=['showcase', 'slot_number'], name='unique_slot_per_showcase'),
            models.UniqueConstraint(fields=['showcase', 'visible_code'], name='unique_visible_code_per_showcase'),
        ]
        ordering = ['showcase', 'slot_number']

    def get_public_url(self) -> str:
        base = getattr(settings, 'SHOWCASE_BASE_URL', 'https://subarashii-academy.onrender.com/v/').rstrip('/')
        return f"{base}/{self.qr_token}"

    @property
    def current_assignment(self):
        """Devuelve la asignación activa actual del slot, si existe."""
        return self.assignments.filter(is_active=True).select_related('item__print__card').first()

    @property
    def current_item(self):
        assignment = self.current_assignment
        return assignment.item if assignment else None

    def __str__(self) -> str:
        return f"{self.showcase.code} - Slot {self.visible_code}"


class SlotAssignment(models.Model):
    slot = models.ForeignKey(
        ShowcaseSlot,
        on_delete=models.PROTECT,
        related_name='assignments',
        verbose_name='Espacio (Slot)'
    )
    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name='slot_assignments',
        verbose_name='Carta Física'
    )
    assigned_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Asignación'
    )
    unassigned_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Retiro'
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name='Asignación Activa'
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_slots',
        verbose_name='Asignado Por'
    )
    unassigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='unassigned_slots',
        verbose_name='Retirado Por'
    )
    notes = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Notas'
    )

    class Meta:
        verbose_name = 'Asignación de Carta a Slot'
        verbose_name_plural = 'Historial de Asignaciones a Slots'
        constraints = [
            models.UniqueConstraint(
                fields=['slot'],
                condition=models.Q(is_active=True),
                name='unique_active_assignment_per_slot'
            ),
            models.UniqueConstraint(
                fields=['item'],
                condition=models.Q(is_active=True),
                name='unique_active_assignment_per_item'
            )
        ]
        ordering = ['-assigned_at']

    def clean(self):
        super().clean()
        if self.is_active:
            # Validar que el slot no tenga otra asignación activa distinta a esta
            existing_slot = SlotAssignment.objects.filter(slot=self.slot, is_active=True)
            if self.pk:
                existing_slot = existing_slot.exclude(pk=self.pk)
            if existing_slot.exists():
                raise ValidationError("Este slot ya tiene una carta activa asignada.")

            # Validar que el item no esté asignado en otro slot
            existing_item = SlotAssignment.objects.filter(item=self.item, is_active=True)
            if self.pk:
                existing_item = existing_item.exclude(pk=self.pk)
            if existing_item.exists():
                raise ValidationError("Esta carta física ya está asignada a otro slot activo.")

    def unassign(self, user=None, reason="Retiro de vitrina"):
        """Desasigna la carta del slot de forma segura."""
        self.is_active = False
        self.unassigned_at = timezone.now()
        self.unassigned_by = user
        if reason:
            self.notes = f"{self.notes} | {reason}".strip(" |")
        self.save()

        # Actualizar estado de inventario
        self.item.status = InventoryItem.Status.IN_STOCK
        self.item.location = "Bodega (Retirada de vitrina)"
        self.item.save()

    def __str__(self) -> str:
        state = "Activa" if self.is_active else "Finalizada"
        return f"{self.slot.visible_code} -> {self.item.sku} ({state})"
