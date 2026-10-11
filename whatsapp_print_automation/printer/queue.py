from __future__ import annotations

import hashlib
import logging
import queue
import threading
from dataclasses import dataclass
from pathlib import Path

from config import AppConfig
from printer.service import PrinterService
from state import StateStore


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PrintJob:
    job_id: str
    file_hash: str
    file_path: Path
    contact: str
    printer_key: str


class PrintQueue:
    def __init__(self, config: AppConfig, state: StateStore, printer: PrinterService) -> None:
        self.config = config
        self.state = state
        self.printer = printer
        self._queue: queue.Queue[PrintJob] = queue.Queue()
        self._stop_event = threading.Event()
        self._worker = threading.Thread(target=self._run, name="print-worker", daemon=True)

    def start(self) -> None:
        self._worker.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._queue.put(
            PrintJob(
                job_id="__stop__",
                file_hash="",
                file_path=Path(),
                contact="",
                printer_key="IMP",
            )
        )
        self._worker.join(timeout=10)

    def enqueue(self, file_path: Path, contact: str, printer_key: str) -> bool:
        file_hash = self._hash_file(file_path)
        job_id = hashlib.sha256(f"{file_hash}:{printer_key.upper()}".encode("utf-8")).hexdigest()

        if not self.state.add_job(job_id, file_hash, printer_key.upper(), file_path, contact):
            logger.info(
                "Trabajo duplicado omitido | contacto=%s archivo=%s impresora=%s",
                contact,
                file_path.name,
                printer_key,
            )
            return False

        self._queue.put(PrintJob(job_id, file_hash, file_path, contact, printer_key.upper()))
        logger.info("Trabajo encolado | contacto=%s archivo=%s impresora=%s", contact, file_path.name, printer_key)
        return True

    def _run(self) -> None:
        while not self._stop_event.is_set():
            job = self._queue.get()
            if job.job_id == "__stop__":
                self._queue.task_done()
                break

            try:
                self.state.update_job(job.job_id, "printing")
                self.printer.print_file(job.file_path, job.printer_key)
                moved = self.printer.move_unique(job.file_path, self.config.printed_dir)
                self.state.update_job(job.job_id, "printed", moved)
                logger.info(
                    "Impresion completada | contacto=%s archivo=%s estado=printed",
                    job.contact,
                    moved.name,
                )
            except Exception as exc:
                logger.exception(
                    "Error de impresion | contacto=%s archivo=%s error=%s",
                    job.contact,
                    job.file_path.name,
                    exc,
                )
                moved_path = job.file_path
                if job.file_path.exists():
                    moved_path = self.printer.move_unique(job.file_path, self.config.error_dir)
                self.state.update_job(job.job_id, "error", moved_path, str(exc))
            finally:
                self._queue.task_done()

    @staticmethod
    def _hash_file(file_path: Path) -> str:
        digest = hashlib.sha256()
        with file_path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
