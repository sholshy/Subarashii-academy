from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AttachmentMessage:
    index: int
    message_id: str
    contact: str
    suggested_name: str
    previous_text: str
    extension: str


@dataclass(frozen=True)
class DownloadedAttachment:
    message: AttachmentMessage
    file_name: str
    printer_key: str | None
