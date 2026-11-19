from typing import List, Optional, Tuple, Dict, Any
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.inventory.models import InventoryItem, InventoryMovement
from apps.showcases.models import Showcase, ShowcaseSlot, SlotAssignment

class ShowcaseService:
    @classmethod
    @transaction.atomic
    def create_showcase(
        cls,
        name: str,
        code: str,
        total_rows: int = 4,
        total_columns: int = 8,
        description: str = "",
        contact_whatsapp: str = "+56912345678"
    ) -> Tuple[Showcase, int]:
        """
        Crea una vitrina y genera automáticamente todos sus slots en formato de cuadrícula
        (Filas A..Z, Columnas 01..N) con tokens QR únicos permanentes.
        """
        showcase = Showcase.objects.create(
            name=name,
            code=code.strip().upper(),
            total_rows=total_rows,
            total_columns=total_columns,
            description=description,
            contact_whatsapp=contact_whatsapp
        )

        slots_to_create = []
        slot_number = 1

        for r in range(total_rows):
            # Letra de fila: 0 -> 'A', 1 -> 'B', etc.
            row_letter = chr(65 + r) if r < 26 else f"R{r+1}"
            for c in range(1, total_columns + 1):
                visible_code = f"{showcase.code}-{row_letter}{c:02d}"
                slots_to_create.append(
                    ShowcaseSlot(
                        showcase=showcase,
                        slot_number=slot_number,
                        visible_code=visible_code,
                        is_active=True
                    )
                )
                slot_number += 1

        created_slots = ShowcaseSlot.objects.bulk_create(slots_to_create)
        return showcase, len(created_slots)

    @classmethod
    @transaction.atomic
    def assign_item_to_slot(
        cls,
        slot: ShowcaseSlot,
        item: InventoryItem,
        user = None,
        notes: str = ""
    ) -> SlotAssignment:
        """
        Asigna una carta física de inventario a un slot de vitrina.
        Valida que el slot no esté ocupado y que la carta esté en bodega.
        Actualiza el estado de la carta a IN_SHOWCASE y registra el movimiento.
        """
        if not slot.is_active:
            raise ValidationError(f"El slot {slot.visible_code} se encuentra inactivo.")

        active_slot_assignment = slot.assignments.filter(is_active=True).first()
        if active_slot_assignment:
            raise ValidationError(f"El slot {slot.visible_code} ya tiene asignada la carta {active_slot_assignment.item.sku}.")

        active_item_assignment = item.slot_assignments.filter(is_active=True).first()
        if active_item_assignment:
            raise ValidationError(f"La carta {item.sku} ya está asignada al slot {active_item_assignment.slot.visible_code}.")

        if item.status not in [InventoryItem.Status.IN_STOCK, InventoryItem.Status.IN_SHOWCASE]:
            raise ValidationError(f"La carta {item.sku} no está disponible (Estado actual: {item.get_status_display()}).")

        # Crear asignación activa
        assignment = SlotAssignment.objects.create(
            slot=slot,
            item=item,
            assigned_by=user,
            notes=notes,
            is_active=True
        )

        # Actualizar ubicación y estado del ítem en inventario
        old_status = item.status
        old_location = item.location
        new_location = f"{slot.showcase.name} - Slot {slot.visible_code}"

        item.status = InventoryItem.Status.IN_SHOWCASE
        item.location = new_location
        item.save()

        # Registrar trazabilidad en InventoryMovement
        InventoryMovement.objects.create(
            item=item,
            from_status=old_status,
            to_status=InventoryItem.Status.IN_SHOWCASE,
            from_location=old_location,
            to_location=new_location,
            user=user,
            reason=f"Montaje en vitrina: {slot.visible_code}"
        )

        return assignment

    @classmethod
    @transaction.atomic
    def unassign_slot(
        cls,
        slot: ShowcaseSlot,
        user = None,
        reason: str = "Retiro manual de vitrina"
    ) -> Optional[InventoryItem]:
        """
        Retira la carta activa del slot, devolviéndola al estado IN_STOCK en bodega.
        El QR del slot permanece inalterado.
        """
        active_assignment = slot.assignments.filter(is_active=True).first()
        if not active_assignment:
            return None

        item = active_assignment.item

        # Cerrar asignación
        active_assignment.is_active = False
        active_assignment.unassigned_at = timezone.now()
        active_assignment.unassigned_by = user
        if reason:
            active_assignment.notes = f"{active_assignment.notes} | {reason}".strip(" |")
        active_assignment.save()

        # Devolver a bodega
        old_status = item.status
        old_location = item.location
        new_location = "Bodega Principal (Retirada de vitrina)"

        item.status = InventoryItem.Status.IN_STOCK
        item.location = new_location
        item.save()

        # Trazabilidad
        InventoryMovement.objects.create(
            item=item,
            from_status=old_status,
            to_status=InventoryItem.Status.IN_STOCK,
            from_location=old_location,
            to_location=new_location,
            user=user,
            reason=f"Retiro de slot {slot.visible_code}: {reason}"
        )

        return item

    @classmethod
    def get_showcase_matrix(cls, showcase: Showcase) -> List[Dict[str, Any]]:
        """
        Genera la matriz bidimensional de filas y columnas de la vitrina
        con datos optimizados para el renderizado visual de la cuadrícula física.
        """
        slots = list(
            showcase.slots.prefetch_related(
                'assignments__item__print__card'
            ).order_by('slot_number')
        )

        # Mapa de asignaciones activas
        active_assignments = {
            a.slot_id: a
            for a in SlotAssignment.objects.filter(
                slot__showcase=showcase,
                is_active=True
            ).select_related('item__print__card')
        }

        matrix = []
        slot_idx = 0
        total_rows = showcase.total_rows
        total_cols = showcase.total_columns

        for r in range(total_rows):
            row_letter = chr(65 + r) if r < 26 else f"R{r+1}"
            row_slots = []
            for c in range(total_cols):
                if slot_idx < len(slots):
                    slot = slots[slot_idx]
                    assignment = active_assignments.get(slot.id)
                    row_slots.append({
                        'slot': slot,
                        'has_card': assignment is not None,
                        'assignment': assignment,
                        'item': assignment.item if assignment else None
                    })
                    slot_idx += 1
            matrix.append({
                'row_label': f"Fila {row_letter}",
                'row_letter': row_letter,
                'slots': row_slots
            })

        return matrix
