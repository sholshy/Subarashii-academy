import hmac
import hashlib
import json
from decimal import Decimal
from integrations.ygoprodeck.client import YGOPRODeckClient
from integrations.tuu.client import TUUPaymentClient

class TestIntegrationsMocks:
    def test_ygoprodeck_parser(self):
        client = YGOPRODeckClient()
        raw_card = {
            "id": 89631139,
            "name": "Blue-Eyes White Dragon",
            "type": "Normal Monster",
            "desc": "This legendary dragon is a powerful engine of destruction.",
            "race": "Dragon",
            "attribute": "LIGHT",
            "atk": 3000,
            "def": 2500,
            "level": 8,
            "card_images": [{"image_url": "https://images.ygoprodeck.com/images/cards/89631139.jpg"}],
            "card_sets": [{"set_name": "Legend of Blue Eyes White Dragon", "set_code": "LOB-001"}]
        }
        parsed = client._parse_card(raw_card)
        assert parsed.ygoprodeck_id == 89631139
        assert parsed.name == "Blue-Eyes White Dragon"
        assert parsed.atk == 3000
        assert parsed.image_url == "https://images.ygoprodeck.com/images/cards/89631139.jpg"

    def test_tuu_webhook_signature_verification(self):
        secret = "tuu_test_webhook_secret_key_123"
        client = TUUPaymentClient(webhook_secret=secret)

        payload_dict = {
            "event": "payment.succeeded",
            "order_number": "ORD-12345",
            "status": "PAID",
            "amount": "25000"
        }
        payload_bytes = json.dumps(payload_dict).encode('utf-8')

        # Generate valid HMAC signature
        valid_signature = hmac.new(
            secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()

        result = client.verify_webhook(payload_bytes, valid_signature)
        assert result.is_valid is True
        assert result.order_number == "ORD-12345"
        assert result.amount == Decimal("25000")

        # Invalid signature must be rejected
        invalid_result = client.verify_webhook(payload_bytes, "invalid_signature_hex")
        assert invalid_result.is_valid is False
