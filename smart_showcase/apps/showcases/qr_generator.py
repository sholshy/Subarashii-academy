import io
import math
from typing import List, Optional
import qrcode
from PIL import Image, ImageDraw, ImageFont
from django.conf import settings
from apps.showcases.models import Showcase, ShowcaseSlot

class QRGeneratorService:
    @classmethod
    def generate_slot_qr_image(
        cls,
        slot: ShowcaseSlot,
        base_url: Optional[str] = None,
        box_size: int = 10,
        border: int = 2
    ) -> io.BytesIO:
        """
        Genera una etiqueta visual con el código QR del slot, lista para descarga o visualización.
        Incluye el logo/texto de Subarashii, el código legible (ej: VIT01-A01) y la instrucción.
        """
        target_url = slot.get_public_url()

        # Generar QR puro
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=box_size,
            border=border
        )
        qr.add_data(target_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

        # Dimensiones de la etiqueta compuesta
        qr_w, qr_h = qr_img.size
        card_w = qr_w + 40
        card_h = qr_h + 120

        card = Image.new('RGB', (card_w, card_h), color='#FFFFFF')
        draw = ImageDraw.Draw(card)

        # Cargar fuentes por defecto
        try:
            font_title = ImageFont.truetype("arialbd.ttf", 22)
            font_code = ImageFont.truetype("arialbd.ttf", 26)
            font_subtitle = ImageFont.truetype("arial.ttf", 14)
        except IOError:
            font_title = ImageFont.load_default()
            font_code = ImageFont.load_default()
            font_subtitle = ImageFont.load_default()

        # Encabezado: Marca
        title_text = "SUBARASHII STORE"
        draw.text(((card_w - 200) // 2, 14), title_text, fill="#0f172a", font=font_title)

        # Pegar QR en el centro
        qr_x = (card_w - qr_w) // 2
        card.paste(qr_img, (qr_x, 45))

        # Banner del código visible
        slot_text = slot.visible_code
        draw.rectangle([(15, qr_h + 50), (card_w - 15, qr_h + 85)], fill="#0f172a")
        draw.text(((card_w - 150) // 2, qr_h + 55), slot_text, fill="#fbbf24", font=font_code)

        # Subtítulo inferior
        sub_text = "Escanea para ver carta y comprar"
        draw.text(((card_w - 210) // 2, qr_h + 95), sub_text, fill="#475569", font=font_subtitle)

        # Borde exterior de recorte
        draw.rectangle([(0, 0), (card_w - 1, card_h - 1)], outline="#cbd5e1", width=2)

        output = io.BytesIO()
        card.save(output, format='PNG')
        output.seek(0)
        return output

    @classmethod
    def generate_showcase_sheet_a4(
        cls,
        showcase: Showcase,
        slots: Optional[List[ShowcaseSlot]] = None,
        cols: int = 4,
        rows: int = 6
    ) -> io.BytesIO:
        """
        Genera una hoja tamaño A4 (2480 x 3508 px a 300 DPI) con múltiples códigos QR
        en cuadrícula para impresión profesional de etiquetas adhesivas o fichas de vitrina.
        """
        if slots is None:
            slots = list(showcase.slots.filter(is_active=True).order_by('slot_number'))

        # Dimensiones A4 estándar a 300 DPI
        sheet_w = 2480
        sheet_h = 3508
        margin_x = 100
        margin_y = 120

        sheet = Image.new('RGB', (sheet_w, sheet_h), color='#FFFFFF')
        draw = ImageDraw.Draw(sheet)

        try:
            font_header = ImageFont.truetype("arialbd.ttf", 46)
            font_sub = ImageFont.truetype("arial.ttf", 26)
            font_label = ImageFont.truetype("arialbd.ttf", 30)
            font_code = ImageFont.truetype("arialbd.ttf", 36)
        except IOError:
            font_header = ImageFont.load_default()
            font_sub = ImageFont.load_default()
            font_label = ImageFont.load_default()
            font_code = ImageFont.load_default()

        # Título y encabezado de la hoja de vitrina
        header_text = f"SUBARASHII SMART SHOWCASE — {showcase.name.upper()} ({showcase.code})"
        draw.text((margin_x, 40), header_text, fill="#0f172a", font=font_header)
        draw.text((margin_x, 95), f"Lámina A4 de códigos QR permanentes ({len(slots)} slots)", fill="#64748b", font=font_sub)
        draw.line([(margin_x, 135), (sheet_w - margin_x, 135)], fill="#e2e8f0", width=3)

        # Cálculo de celdas
        grid_w = sheet_w - (2 * margin_x)
        grid_h = sheet_h - margin_y - 160
        cell_w = grid_w // cols
        cell_h = grid_h // rows

        slot_idx = 0
        total_slots_on_page = min(len(slots), cols * rows)

        for r in range(rows):
            for c in range(cols):
                if slot_idx >= total_slots_on_page:
                    break

                slot = slots[slot_idx]
                x0 = margin_x + (c * cell_w)
                y0 = margin_y + 60 + (r * cell_h)
                x1 = x0 + cell_w
                y1 = y0 + cell_h

                # Líneas de corte punteadas/guía
                draw.rectangle([(x0 + 8, y0 + 8), (x1 - 8, y1 - 8)], outline="#cbd5e1", width=2)

                # Generar QR para la celda
                qr = qrcode.QRCode(
                    version=None,
                    error_correction=qrcode.constants.ERROR_CORRECT_M,
                    box_size=6,
                    border=1
                )
                qr.add_data(slot.get_public_url())
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

                qw, qh = qr_img.size
                qx = x0 + (cell_w - qw) // 2
                qy = y0 + 35
                sheet.paste(qr_img, (qx, qy))

                # Etiqueta del slot
                code_text = slot.visible_code
                draw.rectangle([(x0 + 20, y1 - 80), (x1 - 20, y1 - 30)], fill="#0f172a")
                draw.text((x0 + (cell_w - 180) // 2, y1 - 72), code_text, fill="#fbbf24", font=font_code)

                slot_idx += 1

        output = io.BytesIO()
        sheet.save(output, format='PNG', dpi=(300, 300))
        output.seek(0)
        return output
