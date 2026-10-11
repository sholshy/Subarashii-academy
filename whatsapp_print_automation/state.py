from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator


class StateStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_messages (
                    message_id TEXT PRIMARY KEY,
                    contact TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS print_jobs (
                    job_id TEXT PRIMARY KEY,
                    file_hash TEXT NOT NULL,
                    printer_key TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    contact TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS print_intents (
                    intent_id TEXT PRIMARY KEY,
                    contact TEXT NOT NULL,
                    printer_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )

    def is_message_processed(self, message_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status FROM processed_messages WHERE message_id = ?",
                (message_id,),
            ).fetchone()
            if row is None:
                return False
            return str(row["status"]).lower() not in {"error", "download_error"}

    def mark_message_processed(self, message_id: str, contact: str, file_name: str, status: str) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO processed_messages(message_id, contact, file_name, status, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (message_id, contact, file_name, status, now),
            )

    def job_exists(self, job_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM print_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            return row is not None

    def add_job(self, job_id: str, file_hash: str, printer_key: str, file_path: Path, contact: str) -> bool:
        now = datetime.now().isoformat(timespec="seconds")
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO print_jobs(job_id, file_hash, printer_key, file_path, contact, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (job_id, file_hash, printer_key, str(file_path), contact, "queued", now, now),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def update_job(self, job_id: str, status: str, file_path: Path | None = None, error: str | None = None) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE print_jobs
                SET status = ?, file_path = COALESCE(?, file_path), updated_at = ?, error = ?
                WHERE job_id = ?
                """,
                (status, str(file_path) if file_path else None, now, error, job_id),
            )

    def save_print_intent(self, intent_id: str, contact: str, printer_key: str, window_minutes: int) -> bool:
        now = datetime.now()
        expires_at = now + timedelta(minutes=window_minutes)
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO print_intents(intent_id, contact, printer_key, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        intent_id,
                        contact,
                        printer_key,
                        now.isoformat(timespec="seconds"),
                        expires_at.isoformat(timespec="seconds"),
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def get_active_print_intent(self, contact: str) -> str | None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT printer_key
                FROM print_intents
                WHERE contact = ? AND expires_at >= ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (contact, now),
            ).fetchone()
            return str(row["printer_key"]) if row else None
