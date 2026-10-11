from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent


def _bool(value: str, default: bool = False) -> bool:
    if value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "si", "sí"}


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else BASE_DIR / path


@dataclass(frozen=True)
class AppConfig:
    whatsapp_url: str
    poll_interval_seconds: int
    headless: bool
    pending_dir: Path
    printed_dir: Path
    error_dir: Path
    log_dir: Path
    session_dir: Path
    state_db: Path
    sumatra_path: Path
    laser_printer_name: str
    color_printer_name: str
    allowed_extensions: set[str]
    print_timeout_seconds: int
    download_timeout_ms: int
    debug_whatsapp_scan: bool
    print_intent_window_minutes: int

    @classmethod
    def load(cls) -> "AppConfig":
        load_dotenv(BASE_DIR / ".env")

        config = cls(
            whatsapp_url=os.getenv("WHATSAPP_URL", "https://web.whatsapp.com/"),
            poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "8")),
            headless=_bool(os.getenv("HEADLESS", "false")),
            pending_dir=_path(os.getenv("PENDING_DIR", "pendientes")),
            printed_dir=_path(os.getenv("PRINTED_DIR", "impresos")),
            error_dir=_path(os.getenv("ERROR_DIR", "errores")),
            log_dir=_path(os.getenv("LOG_DIR", "logs")),
            session_dir=_path(os.getenv("SESSION_DIR", "session")),
            state_db=_path(os.getenv("STATE_DB", "data/state.sqlite3")),
            sumatra_path=_path(os.getenv("SUMATRA_PATH", r"C:\Program Files\SumatraPDF\SumatraPDF.exe")),
            laser_printer_name=os.getenv("LASER_PRINTER_NAME", "Laser"),
            color_printer_name=os.getenv("COLOR_PRINTER_NAME", "Color"),
            allowed_extensions={
                ext.strip().lower()
                for ext in os.getenv("ALLOWED_EXTENSIONS", ".pdf,.jpg,.jpeg,.png").split(",")
                if ext.strip()
            },
            print_timeout_seconds=int(os.getenv("PRINT_TIMEOUT_SECONDS", "120")),
            download_timeout_ms=int(os.getenv("DOWNLOAD_TIMEOUT_SECONDS", "60000")),
            debug_whatsapp_scan=_bool(os.getenv("DEBUG_WHATSAPP_SCAN", "true")),
            print_intent_window_minutes=int(os.getenv("PRINT_INTENT_WINDOW_MINUTES", "10")),
        )
        config.ensure_directories()
        return config

    def ensure_directories(self) -> None:
        for directory in (
            self.pending_dir,
            self.printed_dir,
            self.error_dir,
            self.log_dir,
            self.session_dir,
            self.state_db.parent,
        ):
            directory.mkdir(parents=True, exist_ok=True)
