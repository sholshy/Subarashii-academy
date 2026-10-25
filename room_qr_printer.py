import os
import tempfile
import threading
from datetime import datetime
import qrcode
from PIL import Image, ImageDraw, ImageFont, ImageWin

try:
    import win32ui
    import win32print
    import win32con
    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False


def _get_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    """Helper to locate Windows TrueType fonts with fallback."""
    font_dir = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')
    path = os.path.join(font_dir, name)
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        try:
            return ImageFont.truetype(os.path.join(font_dir, 'arial.ttf'), size)
        except Exception:
            return ImageFont.load_default()


def generate_room_qr_poster(
    room_code: str,
    url: str,
    title: str = "Torneo Subarashii Duel Academy",
    format_name: str = "EDISON",
    store_name: str = "Subarashii Duel Academy",
    date_str: str | None = None
) -> Image.Image:
    """
    Generates a high-resolution, print-ready A4 poster (2480 x 3508 px @ 300 DPI)
    suitable for hanging on store walls so players can easily scan the room QR.
    """
    if not date_str:
        date_str = datetime.now().strftime("%d-%m-%Y")

    w, h = 2480, 3508
    img = Image.new('RGB', (w, h), 'white')
    draw = ImageDraw.Draw(img)

    margin = 80
    # Outer dark border
    draw.rectangle([margin, margin, w - margin, h - margin], outline='#0f172a', width=16)
    # Inner theme border
    draw.rectangle([margin + 20, margin + 20, w - margin - 20, h - margin - 20], outline='#0284c7', width=6)

    # Header / Branding
    f_brand = _get_font('arialbd.ttf', 110)
    f_sub = _get_font('arialbd.ttf', 46)
    draw.text((w / 2, 220), 'DUELORAPIDO.CL', fill='#0f172a', font=f_brand, anchor='mm')
    draw.text((w / 2, 310), store_name.upper(), fill='#0284c7', font=f_sub, anchor='mm')
    draw.line([(margin + 60, 370), (w - margin - 60, 370)], fill='#cbd5e1', width=4)

    # Event badge & title
    f_badge = _get_font('arialbd.ttf', 44)
    badge_w = 600
    badge_box = [int(w / 2 - badge_w / 2), 410, int(w / 2 + badge_w / 2), 480]
    draw.rounded_rectangle(badge_box, radius=18, fill='#e0f2fe', outline='#0284c7', width=3)
    draw.text((w / 2, 445), f"FORMATO {format_name.upper()}", fill='#0369a1', font=f_badge, anchor='mm')

    f_title = _get_font('arialbd.ttf', 54)
    draw.text((w / 2, 535), title, fill='#1e293b', font=f_title, anchor='mm')

    # Big CTA
    f_cta = _get_font('arialbd.ttf', 72)
    draw.text((w / 2, 630), '¡ESCANEA PARA UNIRTE AL TORNEO!', fill='#0f172a', font=f_cta, anchor='mm')

    # QR Code generation (High Quality)
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=32,
        border=2
    )
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color='black', back_color='white').convert('RGB')
    qr_w, qr_h = qr_img.size

    # Target QR size: ~1350 x 1350 px
    target_qr_size = 1350
    if qr_w != target_qr_size:
        qr_img = qr_img.resize((target_qr_size, target_qr_size), Image.Resampling.NEAREST)
        qr_w, qr_h = qr_img.size

    qr_x = int((w - qr_w) / 2)
    qr_y = 700

    # Draw QR background card / subtle shadow frame
    qr_frame = [qr_x - 18, qr_y - 18, qr_x + qr_w + 18, qr_y + qr_h + 18]
    draw.rounded_rectangle(qr_frame, radius=24, fill='#ffffff', outline='#cbd5e1', width=4)
    img.paste(qr_img, (qr_x, qr_y))

    # PIN Card Box
    pin_top = qr_y + qr_h + 60
    pin_box = [int(w / 2 - 580), pin_top, int(w / 2 + 580), pin_top + 300]
    draw.rounded_rectangle(pin_box, radius=32, fill='#f8fafc', outline='#0284c7', width=6)

    f_pin_lbl = _get_font('arialbd.ttf', 40)
    f_pin = _get_font('arialbd.ttf', 130)
    clean_code = str(room_code).lstrip('#')
    draw.text((w / 2, pin_top + 70), 'PIN DE SALA / TORNEO', fill='#64748b', font=f_pin_lbl, anchor='mm')
    draw.text((w / 2, pin_top + 185), f"#{clean_code}", fill='#0f172a', font=f_pin, anchor='mm')

    # Instructions / Steps
    steps_y = pin_top + 360
    f_step_num = _get_font('arialbd.ttf', 52)
    f_step = _get_font('arialbd.ttf', 46)

    steps = [
        ("1", "Abre la cámara de tu celular o app lectora de QR"),
        ("2", f"Escanea el código o entra a duelorapido.cl/unirse"),
        ("3", "Ingresa tu nombre y verás tu mesa y pareos en vivo")
    ]

    for i, (num, txt) in enumerate(steps):
        y = steps_y + (i * 96)
        # Circle badge
        draw.ellipse([w / 2 - 820, y - 40, w / 2 - 740, y + 42], fill='#0284c7')
        draw.text((w / 2 - 780, y + 2), num, fill='white', font=f_step_num, anchor='mm')
        draw.text((w / 2 - 710, y + 2), txt, fill='#1e293b', font=f_step, anchor='lm')

    # Footer
    draw.line([(margin + 60, h - 220), (w - margin - 60, h - 220)], fill='#cbd5e1', width=4)
    f_foot = _get_font('arial.ttf', 38)
    draw.text((w / 2, h - 160), f"Duelorapido.cl  •  {date_str}  •  Sistema Oficial de Torneos", fill='#64748b', font=f_foot, anchor='mm')

    return img


def get_system_printers() -> list[str]:
    """Returns list of installed Windows printer names, or empty list if unavailable."""
    if not PYWIN32_AVAILABLE:
        return []
    try:
        printers = [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
        return printers
    except Exception:
        return []


def get_default_printer_name() -> str | None:
    """Returns the default Windows printer name."""
    if not PYWIN32_AVAILABLE:
        return None
    try:
        return win32print.GetDefaultPrinter()
    except Exception:
        return None


def print_image_to_printer(image: Image.Image, printer_name: str | None = None, doc_name: str = "Cartel_QR_Sala") -> None:
    """
    Sends a PIL Image directly to a Windows printer using GDI / pywin32,
    scaling proportionally to fit the printable area.
    """
    if not PYWIN32_AVAILABLE:
        raise RuntimeError("pywin32 no está instalado o disponible en este sistema.")

    target_printer = printer_name or get_default_printer_name()
    if not target_printer:
        raise RuntimeError("No se detectó ninguna impresora predeterminada en el sistema.")

    printer_dc = win32ui.CreateDC()
    printer_dc.CreatePrinterDC(target_printer)

    img_rgb = image.convert('RGB')
    printable_w = printer_dc.GetDeviceCaps(win32con.HORZRES)
    printable_h = printer_dc.GetDeviceCaps(win32con.VERTRES)

    scale = min(printable_w / img_rgb.width, printable_h / img_rgb.height)
    out_w = int(img_rgb.width * scale)
    out_h = int(img_rgb.height * scale)
    left = int((printable_w - out_w) / 2)
    top = int((printable_h - out_h) / 2)

    try:
        printer_dc.StartDoc(doc_name)
        printer_dc.StartPage()
        dib = ImageWin.Dib(img_rgb)
        dib.draw(printer_dc.GetHandleOutput(), (left, top, left + out_w, top + out_h))
        printer_dc.EndPage()
        printer_dc.EndDoc()
    finally:
        printer_dc.DeleteDC()


def export_poster_pdf(image: Image.Image, output_path: str) -> str:
    """Saves the poster Image as an A4 PDF file."""
    image.convert('RGB').save(output_path, "PDF", resolution=300.0)
    return output_path
