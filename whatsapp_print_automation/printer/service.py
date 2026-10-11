from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageWin

from config import AppConfig

try:
    import win32con
    import win32print
    import win32ui
except ImportError:  # pragma: no cover - only valid outside Windows/dev envs.
    win32con = None
    win32print = None
    win32ui = None


logger = logging.getLogger(__name__)


class PrintError(RuntimeError):
    pass


class PrinterService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def print_file(self, file_path: Path, printer_key: str) -> None:
        suffix = file_path.suffix.lower()
        printer_name = self.resolve_printer_name(printer_key)
        logger.info("Imprimiendo archivo=%s impresora=%s", file_path.name, printer_name or "predeterminada")

        if suffix == ".pdf":
            self._print_pdf(file_path, printer_name)
            return

        if suffix in {".jpg", ".jpeg", ".png"}:
            self._print_image(file_path, printer_name)
            return

        raise PrintError(f"Extension no soportada para impresion: {suffix}")

    def resolve_printer_name(self, printer_key: str) -> str | None:
        normalized = printer_key.upper()
        if normalized == "IMP":
            return None
        if normalized == "LASER":
            return self.config.laser_printer_name
        if normalized == "COLOR":
            return self.config.color_printer_name
        raise PrintError(f"Clave de impresora invalida: {printer_key}")

    def _print_pdf(self, file_path: Path, printer_name: str | None) -> None:
        if not self.config.sumatra_path.exists():
            raise PrintError(f"No se encontro SumatraPDF en {self.config.sumatra_path}")

        command = [
            str(self.config.sumatra_path),
            "-silent",
            "-exit-on-print",
        ]
        if printer_name:
            command.extend(["-print-to", printer_name])
        else:
            command.append("-print-to-default")
        command.append(str(file_path))

        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.config.print_timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise PrintError(f"Tiempo agotado imprimiendo PDF: {file_path.name}") from exc

        if result.returncode != 0:
            details = (result.stderr or result.stdout or "").strip()
            raise PrintError(f"SumatraPDF fallo con codigo {result.returncode}: {details}")

    def _print_image(self, file_path: Path, printer_name: str | None) -> None:
        if win32print is None or win32ui is None or win32con is None:
            raise PrintError("pywin32 no esta disponible; no se pueden imprimir imagenes en Windows")

        target_printer = printer_name or win32print.GetDefaultPrinter()
        if not target_printer:
            raise PrintError("No hay impresora predeterminada configurada")

        printer_dc = win32ui.CreateDC()
        printer_dc.CreatePrinterDC(target_printer)

        image = Image.open(file_path).convert("RGB")
        printable_width = printer_dc.GetDeviceCaps(win32con.HORZRES)
        printable_height = printer_dc.GetDeviceCaps(win32con.VERTRES)
        image_width, image_height = image.size
        scale = min(printable_width / image_width, printable_height / image_height)
        output_width = int(image_width * scale)
        output_height = int(image_height * scale)
        left = int((printable_width - output_width) / 2)
        top = int((printable_height - output_height) / 2)

        try:
            printer_dc.StartDoc(file_path.name)
            printer_dc.StartPage()
            dib = ImageWin.Dib(image)
            dib.draw(printer_dc.GetHandleOutput(), (left, top, left + output_width, top + output_height))
            printer_dc.EndPage()
            printer_dc.EndDoc()
        except Exception as exc:
            raise PrintError(f"Error imprimiendo imagen {file_path.name}: {exc}") from exc
        finally:
            printer_dc.DeleteDC()
            image.close()

    @staticmethod
    def move_unique(source: Path, destination_dir: Path) -> Path:
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / source.name
        if not destination.exists():
            shutil.move(str(source), str(destination))
            return destination

        stem = source.stem
        suffix = source.suffix
        counter = 1
        while True:
            candidate = destination_dir / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                shutil.move(str(source), str(candidate))
                return candidate
            counter += 1
