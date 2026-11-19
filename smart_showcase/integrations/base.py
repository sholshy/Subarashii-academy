from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from decimal import Decimal

@dataclass
class CatalogCardData:
    ygoprodeck_id: Optional[int]
    name: str
    card_type: str
    description: str
    race: str
    attribute: Optional[str]
    atk: Optional[int]
    def_points: Optional[int]
    level: Optional[int]
    scale: Optional[int]
    link_val: Optional[int]
    archetype: Optional[str]
    card_sets: List[Dict[str, Any]]
    image_url: Optional[str]

@dataclass
class PriceData:
    card_code: str
    reference_price_usd: Optional[Decimal]
    source: str
    last_updated: str

@dataclass
class PaymentInitiationResult:
    success: bool
    transaction_id: str
    payment_url: Optional[str]
    raw_response: Dict[str, Any]
    error_message: Optional[str] = None

@dataclass
class WebhookVerificationResult:
    is_valid: bool
    event_type: str
    order_number: Optional[str]
    status: str
    amount: Optional[Decimal]
    raw_payload: Dict[str, Any]

class BaseCatalogProvider(ABC):
    @abstractmethod
    def search_by_name(self, name: str) -> List[CatalogCardData]:
        """Busca cartas por nombre exacto o aproximado."""
        pass

    @abstractmethod
    def get_by_id(self, card_id: int) -> Optional[CatalogCardData]:
        """Obtiene una carta por su identificador único."""
        pass

    @abstractmethod
    def search_by_set_code(self, set_code: str) -> List[CatalogCardData]:
        """Busca cartas por código de set/expansión."""
        pass

class BasePricingProvider(ABC):
    @abstractmethod
    def get_price(self, print_code: str, tcgplayer_id: Optional[str] = None) -> Optional[PriceData]:
        """Obtiene el precio de referencia de mercado en USD."""
        pass

class BasePaymentProvider(ABC):
    @abstractmethod
    def create_checkout_session(
        self,
        order_number: str,
        amount: Decimal,
        customer_email: str,
        return_url: str,
        webhook_url: str,
        idempotency_key: str
    ) -> PaymentInitiationResult:
        """Crea una sesión o intento de pago seguro en la pasarela."""
        pass

    @abstractmethod
    def verify_webhook(self, payload: bytes, signature_header: str) -> WebhookVerificationResult:
        """Valida la firma criptográfica del webhook y extrae el resultado."""
        pass

    @abstractmethod
    def check_transaction_status(self, transaction_id: str) -> Dict[str, Any]:
        """Consulta directamente a la pasarela el estado de una transacción."""
        pass
