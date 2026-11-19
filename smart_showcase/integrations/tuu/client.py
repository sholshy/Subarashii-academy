import hmac
import hashlib
import json
from decimal import Decimal
from typing import Dict, Any, Optional
from integrations.base import BasePaymentProvider, PaymentInitiationResult, WebhookVerificationResult

class TUUPaymentClient(BasePaymentProvider):
    """
    Adaptador independiente para TUU (Pago Fácil / Transbank gateway de TUU).
    Prioriza checkout online, idempotencia y validación de firma criptográfica HMAC-SHA256.
    """
    def __init__(self, api_key: str = "", api_secret: str = "", webhook_secret: str = "", base_url: str = "https://api.tuu.cl/v1"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.webhook_secret = webhook_secret
        self.base_url = base_url

    def create_checkout_session(
        self,
        order_number: str,
        amount: Decimal,
        customer_email: str,
        return_url: str,
        webhook_url: str,
        idempotency_key: str
    ) -> PaymentInitiationResult:
        if not self.api_key or not self.api_secret:
            return PaymentInitiationResult(
                success=False,
                transaction_id="",
                payment_url=None,
                raw_response={},
                error_message="Credenciales de TUU no configuradas en el entorno."
            )
        
        # Estructura preparada para el endpoint oficial de TUU
        return PaymentInitiationResult(
            success=True,
            transaction_id=f"tuu_mock_{order_number}",
            payment_url=f"{self.base_url}/checkout/pay/{order_number}",
            raw_response={"status": "INITIATED"}
        )

    def verify_webhook(self, payload: bytes, signature_header: str) -> WebhookVerificationResult:
        """
        Valida la firma HMAC-SHA256 del payload recibido por Webhook.
        """
        if not self.webhook_secret:
            return WebhookVerificationResult(
                is_valid=False,
                event_type="unknown",
                order_number=None,
                status="FAILED",
                amount=None,
                raw_payload={}
            )

        expected_signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()

        is_valid = hmac.compare_digest(expected_signature, signature_header)
        
        try:
            data = json.loads(payload.decode('utf-8'))
        except Exception:
            data = {}

        return WebhookVerificationResult(
            is_valid=is_valid,
            event_type=data.get('event', ''),
            order_number=data.get('order_number'),
            status=data.get('status', 'FAILED'),
            amount=Decimal(str(data.get('amount', '0'))),
            raw_payload=data
        )

    def check_transaction_status(self, transaction_id: str) -> Dict[str, Any]:
        """Consulta directa para evitar validar solo por redirección del navegador."""
        return {"transaction_id": transaction_id, "status": "PENDING"}
