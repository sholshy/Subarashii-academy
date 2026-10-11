from __future__ import annotations

import logging
import sys


def _check_dependencies() -> None:
    missing: list[str] = []
    for module_name, package_name in (
        ("dotenv", "python-dotenv"),
        ("playwright", "playwright"),
        ("PIL", "Pillow"),
    ):
        try:
            __import__(module_name)
        except ModuleNotFoundError:
            missing.append(package_name)

    if missing:
        packages = ", ".join(missing)
        print(
            "\nFaltan dependencias de Python: "
            f"{packages}\n\n"
            "Ejecuta estos comandos desde la carpeta whatsapp_print_automation:\n\n"
            "  py -3.12 -m venv .venv\n"
            "  .\\.venv\\Scripts\\Activate.ps1\n"
            "  python -m pip install --upgrade pip\n"
            "  pip install -r requirements.txt\n"
            "  python -m playwright install chromium\n\n"
            "Luego inicia la app con:\n\n"
            "  python main.py\n",
            file=sys.stderr,
        )
        raise SystemExit(1)


_check_dependencies()

from config import AppConfig
from logging_config import setup_logging
from printer.queue import PrintQueue
from printer.service import PrinterService
from state import StateStore
from whatsapp.client import WhatsAppClient


logger = logging.getLogger(__name__)


def main() -> None:
    config = AppConfig.load()
    setup_logging(config.log_dir)

    state = StateStore(config.state_db)
    printer_service = PrinterService(config)
    print_queue = PrintQueue(config, state, printer_service)
    client = WhatsAppClient(config, state, print_queue)

    print_queue.start()
    try:
        client.run_forever()
    except KeyboardInterrupt:
        logger.info("Cierre solicitado por usuario")
    finally:
        client.close()
        print_queue.stop()
        logger.info("Aplicacion detenida")


if __name__ == "__main__":
    main()
