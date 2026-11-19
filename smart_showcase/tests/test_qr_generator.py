import pytest
from PIL import Image
from apps.showcases.models import Showcase, ShowcaseSlot
from apps.showcases.qr_generator import QRGeneratorService

@pytest.mark.django_db
class TestQRGenerator:
    @pytest.fixture
    def sample_showcase(self):
        showcase = Showcase.objects.create(name="Vitrina QR Test", code="VQR", total_rows=2, total_columns=2)
        ShowcaseSlot.objects.create(showcase=showcase, slot_number=1, visible_code="VQR-A01")
        ShowcaseSlot.objects.create(showcase=showcase, slot_number=2, visible_code="VQR-A02")
        return showcase

    def test_generate_slot_qr_image(self, sample_showcase):
        slot = sample_showcase.slots.first()
        buffer = QRGeneratorService.generate_slot_qr_image(slot)
        assert buffer is not None

        # Verify PIL can open and parse it as a valid image
        img = Image.open(buffer)
        assert img.format == 'PNG'
        assert img.size[0] > 100
        assert img.size[1] > 100

    def test_generate_showcase_sheet_a4(self, sample_showcase):
        buffer = QRGeneratorService.generate_showcase_sheet_a4(sample_showcase, cols=2, rows=2)
        assert buffer is not None

        img = Image.open(buffer)
        assert img.format == 'PNG'
        # A4 300 DPI dimensions
        assert img.size == (2480, 3508)
