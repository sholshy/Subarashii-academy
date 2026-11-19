import uuid
from typing import List, Optional
from datetime import date
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.catalog.models import CardPrint
from apps.inventory.models import InventoryItem, InventoryMovement

class InventoryService:
    @classmethod
    @transaction.atomic
    def create_item(
        cls,
        card_print: CardPrint,
        condition: str,
        acquisition_cost: Decimal,
        acquisition_date: Optional[date] = None,
        location: str = "Bodega Principal",
        notes: str = "",
        user = None,
        sku: Optional[str] = None
    ) -> InventoryItem:
        """
        Crea un ejemplar físico individual, garantizando SKU y registrando
        el movimiento de alta inicial.
        """
        if not acquisition_date:
            acquisition_date = date.today()

        if not sku:
            sku = f"SUB-{uuid.uuid4().hex[:10].upper()}"

        item = InventoryItem.objects.create(
            sku=sku,
            print=card_print,
            condition=condition,
            acquisition_cost=acquisition_cost,
            acquisition_date=acquisition_date,
            status=InventoryItem.Status.IN_STOCK,
            location=location,
            notes=notes
        )

        # Registro del movimiento inicial
        InventoryMovement.objects.create(
            item=item,
            from_status="",
            to_status=InventoryItem.Status.IN_STOCK,
            from_location="",
            to_location=location,
            user=user,
            reason="Alta inicial en inventario"
        )

        return item

    @classmethod
    @transaction.atomic
    def bulk_create_items(
        cls,
        card_print: CardPrint,
        quantity: int,
        condition: str,
        acquisition_cost: Decimal,
        acquisition_date: Optional[date] = None,
        location: str = "Bodega Principal",
        notes: str = "",
        user = None
    ) -> List[InventoryItem]:
        """Crea múltiples ejemplares físicos con SKUs y trazabilidad individual."""
        if quantity < 1:
            raise ValidationError("La cantidad a crear debe ser al menos 1.")

        created_items = []
        for _ in range(quantity):
            item = cls.create_item(
                card_print=card_print,
                condition=condition,
                acquisition_cost=acquisition_cost,
                acquisition_date=acquisition_date,
                location=location,
                notes=notes,
                user=user
            )
            created_items.append(item)
        return created_items

    @classmethod
    @transaction.atomic
    def update_item_status(
        cls,
        item: InventoryItem,
        new_status: str,
        new_location: Optional[str] = None,
        user = None,
        reason: str = ""
    ) -> InventoryItem:
        """
        Modifica el estado físico y ubicación del ejemplar registrando la auditoría.
        """
        old_status = item.status
        old_location = item.location
        loc = new_location if new_location is not None else old_location

        if old_status == new_status and old_location == loc:
            return item

        item.status = new_status
        item.location = loc
        item.save()

        InventoryMovement.objects.create(
            item=item,
            from_status=old_status,
            to_status=new_status,
            from_location=old_location,
            to_location=loc,
            user=user,
            reason=reason or f"Cambio de estado: {old_status} -> {new_status}"
        )

        return item
