from __future__ import annotations

import logging
import re
import time
import unicodedata
from pathlib import Path
from typing import Any

from playwright.sync_api import BrowserContext, Page, Playwright, TimeoutError as PlaywrightTimeoutError, sync_playwright

from config import AppConfig
from printer.queue import PrintQueue
from state import StateStore
from whatsapp.models import AttachmentMessage


logger = logging.getLogger(__name__)

CHAT_LIST_SELECTOR = "#pane-side"
CHAT_ROWS_SELECTOR = "#pane-side [role='listitem'], #pane-side [role='row']"
MESSAGE_SELECTOR = "div[data-testid='msg-container'], div.message-in, div.message-out"
DEFAULT_PRINT_PHRASE = "Hola, quiero imprimir estos documentos"
PRINTER_KEY_PATTERN = re.compile(r"\b(LASER|COLOR)\b", re.IGNORECASE)
SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._ -]+")


class WhatsAppClient:
    def __init__(self, config: AppConfig, state: StateStore, print_queue: PrintQueue) -> None:
        self.config = config
        self.state = state
        self.print_queue = print_queue
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._chat_cooldowns: dict[str, float] = {}

    def run_forever(self) -> None:
        with sync_playwright() as playwright:
            self._playwright = playwright
            self._context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.config.session_dir),
                headless=self.config.headless,
                accept_downloads=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--start-maximized",
                ],
            )
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
            self._page.set_default_timeout(15_000)
            self._open_whatsapp()

            logger.info("Monitor de WhatsApp iniciado")
            while True:
                try:
                    self.process_unread_chats()
                except KeyboardInterrupt:
                    raise
                except Exception as exc:
                    logger.exception("Error en ciclo de monitoreo: %s", exc)
                time.sleep(self.config.poll_interval_seconds)

    def close(self) -> None:
        if self._context:
            self._context.close()

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("WhatsAppClient no ha sido iniciado")
        return self._page

    def _open_whatsapp(self) -> None:
        self.page.goto(self.config.whatsapp_url, wait_until="domcontentloaded")
        logger.info("Abriendo WhatsApp Web. Si aparece QR, escanealo desde el telefono.")
        self._wait_until_logged_in()

    def _wait_until_logged_in(self) -> None:
        # Cuando no hay sesion, WhatsApp muestra el QR. Dejamos la ventana abierta hasta que aparezca la lista de chats.
        login_selectors = [
            "div[aria-label='Chat list']",
            "div[aria-label='Lista de chats']",
            "div[role='grid']",
            "#pane-side",
        ]
        selector = ", ".join(login_selectors)
        self.page.wait_for_selector(selector, timeout=0)
        logger.info("Sesion de WhatsApp lista")

    def process_unread_chats(self) -> None:
        chats = self._find_unread_chats()
        if not chats:
            return

        pending_chats = [
            chat
            for chat in chats
            if self._chat_cooldowns.get(chat.get("contact") or "Contacto sin nombre", 0) <= time.time()
        ]
        if not pending_chats:
            return

        logger.info("Chats con mensajes nuevos detectados: %s", len(pending_chats))
        for chat in pending_chats:
            try:
                contact = chat.get("contact") or "Contacto sin nombre"
                self._open_chat_by_index(int(chat["index"]))
                processed_count = self._process_current_chat(contact)
                if processed_count == 0:
                    self._chat_cooldowns[contact] = time.time() + 60
            except Exception as exc:
                logger.exception("No se pudo procesar chat %s: %s", chat, exc)

    def _find_unread_chats(self) -> list[dict[str, Any]]:
        script = """
        () => {
            const pane = document.querySelector("#pane-side");
            if (!pane) return [];

            const unreadRegex = /(unread|no le(?:i|\\u00ed)do|sin leer|mensaje nuevo|mensajes nuevos)/i;
            const rows = Array.from(pane.querySelectorAll("[role='listitem'], [role='row']"));
            return rows.map((row, index) => {
                const text = row.innerText || "";
                const labels = Array.from(row.querySelectorAll("[aria-label]"))
                    .map(el => el.getAttribute("aria-label") || "")
                    .filter(Boolean);
                const hasUnread = labels.some(label => unreadRegex.test(label));
                if (!hasUnread) return null;
                const title = row.querySelector("span[title], div[title]");
                const contact = title?.getAttribute("title") || text.split("\\n")[0] || "Contacto sin nombre";
                return { index, contact };
            }).filter(Boolean);
        }
        """
        return self.page.evaluate(script)

    def _open_chat_by_index(self, index: int) -> None:
        self._close_side_drawers()
        rows = self.page.locator(CHAT_ROWS_SELECTOR)
        rows.nth(index).click(force=True)
        self.page.wait_for_selector(MESSAGE_SELECTOR, timeout=15_000)
        time.sleep(1)

    def _close_side_drawers(self) -> None:
        for _ in range(2):
            drawer_count = self.page.locator("[data-testid='drawer-right']").count()
            if drawer_count == 0:
                return
            self.page.keyboard.press("Escape")
            time.sleep(0.5)

    def _process_current_chat(self, contact: str) -> int:
        self._store_visible_print_intents(contact)
        messages = self._extract_attachment_messages(contact)
        if not messages:
            logger.info("Chat sin adjuntos compatibles | contacto=%s", contact)
            if self.config.debug_whatsapp_scan:
                self._log_chat_scan_diagnostics(contact)
            return 0

        processed_count = 0
        for message in messages:
            if self.state.is_message_processed(message.message_id):
                continue

            printer_key = self._extract_printer_key(message.previous_text) or self.state.get_active_print_intent(contact)
            try:
                if printer_key:
                    logger.info(
                        "Palabra clave detectada | contacto=%s archivo=%s clave=%s",
                        contact,
                        message.suggested_name,
                        printer_key,
                    )
                downloaded_file = self._download_attachment(message)
                if printer_key:
                    queued = self.print_queue.enqueue(downloaded_file, contact, printer_key)
                    status = f"downloaded_queued_{printer_key}" if queued else "downloaded_duplicate_job"
                else:
                    status = "downloaded_no_print_keyword"

                self.state.mark_message_processed(message.message_id, contact, downloaded_file.name, status)
                logger.info(
                    "Adjunto procesado | contacto=%s archivo=%s estado=%s",
                    contact,
                    downloaded_file.name,
                    status,
                )
                processed_count += 1
            except Exception as exc:
                self.state.mark_message_processed(message.message_id, contact, message.suggested_name, "download_error")
                logger.exception(
                    "Error procesando adjunto | contacto=%s archivo=%s error=%s",
                    contact,
                    message.suggested_name,
                    exc,
                )
                processed_count += 1

        if processed_count == 0:
            logger.info("Adjuntos ya procesados previamente | contacto=%s total=%s", contact, len(messages))
        return processed_count

    def _extract_attachment_messages(self, contact: str) -> list[AttachmentMessage]:
        self._reveal_recent_message_controls()
        allowed = sorted(self.config.allowed_extensions)
        script = """
        ([allowedExtensions, defaultPrintPhrase]) => {
            const messageNodes = Array.from(document.querySelectorAll("div[data-testid='msg-container'], div.message-in, div.message-out"));
            const extensionRegex = new RegExp("(" + allowedExtensions.map(ext => ext.replace(".", "\\\\.")).join("|") + ")$", "i");
            const imageRegex = /(abrir foto|open photo|imagen|image|foto|photo)/i;

            function textOf(node) {
                return (node?.innerText || "").trim();
            }

            function normalize(value) {
                return (value || "")
                    .normalize("NFD")
                    .replace(/[\\u0300-\\u036f]/g, "")
                    .replace(/\\s+/g, " ")
                    .trim()
                    .toLocaleLowerCase();
            }

            function hasPrintIntent(text) {
                const normalized = normalize(text);
                return normalized.includes(normalize(defaultPrintPhrase)) || /\\b(LASER|COLOR)\\b/i.test(text || "");
            }

            function labelsOf(node) {
                return Array.from(node.querySelectorAll("[title], [aria-label], [data-icon]"))
                    .map(el => el.getAttribute("title") || el.getAttribute("aria-label") || el.getAttribute("data-icon") || "")
                    .filter(Boolean);
            }

            function filenameOf(node, index) {
                for (const value of labelsOf(node)) {
                    const clean = value.trim();
                    if (extensionRegex.test(clean)) return clean;
                }
                const match = textOf(node).match(/[A-Za-z0-9._ -]+\\.(pdf|jpg|jpeg|png)/i);
                return match ? match[0].trim() : `adjunto_${index}`;
            }

            const attachments = [];
            let lastIntentText = "";

            messageNodes.forEach((node, index) => {
                const nodeText = textOf(node);
                if (hasPrintIntent(nodeText)) {
                    lastIntentText = nodeText;
                }

                const labels = labelsOf(node);
                const filename = filenameOf(node, index);
                const lower = filename.toLowerCase();
                let extension = allowedExtensions.find(ext => lower.endsWith(ext));
                let suggestedName = filename;
                if (!extension && labels.some(label => imageRegex.test(label)) && allowedExtensions.includes(".jpg")) {
                    extension = ".jpg";
                    suggestedName = `foto_${index}.jpg`;
                }
                if (!extension) return;
                const previous = messageNodes[index - 1];
                const previousText = textOf(previous);
                const intentText = hasPrintIntent(previousText) ? previousText : lastIntentText;
                const id = node.getAttribute("data-id") || node.querySelector("[data-id]")?.getAttribute("data-id") || "";
                attachments.push({
                    index,
                    messageId: id || `${suggestedName}:${textOf(previous)}:${textOf(node)}:${labels.join("|")}`.slice(0, 500),
                    suggestedName,
                    previousText: intentText,
                    extension
                });
            });
            return attachments;
        }
        """
        raw_messages = self.page.evaluate(script, [allowed, DEFAULT_PRINT_PHRASE])
        return [
            AttachmentMessage(
                index=int(raw["index"]),
                message_id=f"{contact}:{raw['messageId']}",
                contact=contact,
                suggested_name=str(raw["suggestedName"]),
                previous_text=str(raw["previousText"]),
                extension=str(raw["extension"]).lower(),
            )
            for raw in raw_messages
        ]

    def _store_visible_print_intents(self, contact: str) -> None:
        script = """
        () => {
            const nodes = Array.from(document.querySelectorAll("div[data-testid='msg-container'], div.message-in, div.message-out"));
            return nodes.map((node, index) => ({
                index,
                messageId: node.getAttribute("data-id") || node.querySelector("[data-id]")?.getAttribute("data-id") || "",
                text: (node.innerText || "").trim()
            })).filter(item => item.text);
        }
        """
        try:
            messages = self.page.evaluate(script)
        except Exception as exc:
            logger.info("No se pudieron escanear intenciones de impresion | contacto=%s error=%s", contact, exc)
            return

        for item in messages:
            text = str(item.get("text") or "")
            printer_key = self._extract_printer_key(text)
            if not printer_key:
                continue
            raw_id = str(item.get("messageId") or f"{item.get('index')}:{text}")[:500]
            intent_id = f"{contact}:{raw_id}"
            saved = self.state.save_print_intent(
                intent_id,
                contact,
                printer_key,
                self.config.print_intent_window_minutes,
            )
            if saved:
                logger.info(
                    "Intencion de impresion registrada | contacto=%s clave=%s ventana_minutos=%s",
                    contact,
                    printer_key,
                    self.config.print_intent_window_minutes,
                )

    def _reveal_recent_message_controls(self) -> None:
        messages = self.page.locator(MESSAGE_SELECTOR)
        count = messages.count()
        start = max(0, count - 25)
        for index in range(start, count):
            try:
                messages.nth(index).hover(timeout=500)
            except Exception:
                continue
        time.sleep(0.5)

    def _log_chat_scan_diagnostics(self, contact: str) -> None:
        script = """
        () => {
            const nodes = Array.from(document.querySelectorAll("div[data-testid='msg-container'], div.message-in, div.message-out"));
            return nodes.slice(-8).map((node, offset) => {
                const labels = Array.from(node.querySelectorAll("[aria-label], [title], [data-icon]"))
                    .map(el => el.getAttribute("aria-label") || el.getAttribute("title") || el.getAttribute("data-icon") || "")
                    .filter(Boolean)
                    .slice(0, 12);
                return {
                    offset,
                    text: (node.innerText || "").trim().slice(0, 250),
                    labels
                };
            });
        }
        """
        try:
            diagnostics = self.page.evaluate(script)
        except Exception as exc:
            logger.info("No se pudo generar diagnostico de chat | contacto=%s error=%s", contact, exc)
            return

        if not diagnostics:
            logger.info("Diagnostico WhatsApp | contacto=%s | no se encontraron nodos de mensajes visibles", contact)
            return

        for item in diagnostics:
            logger.info(
                "Diagnostico WhatsApp | contacto=%s | mensaje=%s | texto=%r | labels=%s",
                contact,
                item.get("offset"),
                item.get("text"),
                item.get("labels"),
            )

    def _download_attachment(self, message: AttachmentMessage) -> Path:
        message_locator = self.page.locator(MESSAGE_SELECTOR).nth(message.index)
        message_locator.hover(timeout=2_000)
        time.sleep(0.3)

        safe_contact = self._safe_filename(message.contact)
        self.config.pending_dir.mkdir(parents=True, exist_ok=True)

        download = None
        is_inline_image = message.suggested_name.startswith("foto_")
        if is_inline_image:
            download = self._download_image_from_viewer(message_locator, message)
        if download is None:
            download = self._download_from_message_node(message_locator, message)
        if download is None and message.extension in {".jpg", ".jpeg", ".png"}:
            download = self._download_image_from_viewer(message_locator, message)
        if download is None:
            if self.config.debug_whatsapp_scan:
                self._log_attachment_diagnostics(message)
            raise RuntimeError(f"No se encontro una accion de descarga para {message.suggested_name}")

        suggested = download.suggested_filename or message.suggested_name
        filename = self._unique_name(self.config.pending_dir, f"{safe_contact}_{self._safe_filename(suggested)}")
        download.save_as(filename)
        return filename

    def _download_from_message_node(self, message_locator: Any, message: AttachmentMessage) -> Any | None:
        selectors = [
            "button[aria-label*='Download'], button[aria-label*='Descargar']",
            "[role='button'][aria-label*='Download'], [role='button'][aria-label*='Descargar']",
            "[title*='Download'], [title*='Descargar']",
            "span[data-icon*='download'], [data-icon*='download']",
            "xpath=.//*[contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚ', 'abcdefghijklmnopqrstuvwxyzáéíóú'), 'descargar')]",
            "xpath=.//*[contains(translate(@title, 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚ', 'abcdefghijklmnopqrstuvwxyzáéíóú'), 'descargar')]",
            f"text={message.suggested_name}",
        ]

        for selector in selectors:
            locator = message_locator.locator(selector).first
            download = self._try_download_click(locator)
            if download is not None:
                return download

        return self._try_download_click(message_locator)

    def _download_image_from_viewer(self, message_locator: Any, message: AttachmentMessage) -> Any | None:
        open_selectors = [
            "[aria-label*='Abrir foto'], [aria-label*='Open photo']",
            "[title*='Abrir foto'], [title*='Open photo']",
        ]

        opened = False
        for selector in open_selectors:
            opener = message_locator.locator(selector).first
            if opener.count() == 0:
                continue
            try:
                opener.click(force=True, timeout=2_000)
                opened = True
                break
            except Exception:
                continue

        if not opened:
            try:
                message_locator.click(force=True, timeout=2_000)
                opened = True
            except Exception:
                return None

        time.sleep(1)
        viewer_selectors = [
            "button[aria-label*='Download'], button[aria-label*='Descargar']",
            "[role='button'][aria-label*='Download'], [role='button'][aria-label*='Descargar']",
            "[title*='Download'], [title*='Descargar']",
            "span[data-icon*='download'], [data-icon*='download']",
            "xpath=//*[contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚ', 'abcdefghijklmnopqrstuvwxyzáéíóú'), 'descargar')]",
            "xpath=//*[contains(translate(@title, 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚ', 'abcdefghijklmnopqrstuvwxyzáéíóú'), 'descargar')]",
        ]

        try:
            for selector in viewer_selectors:
                download = self._try_download_click(self.page.locator(selector).first)
                if download is not None:
                    return download
            return None
        finally:
            self.page.keyboard.press("Escape")
            time.sleep(0.5)

    def _try_download_click(self, locator: Any) -> Any | None:
        try:
            if locator.count() == 0:
                return None
            with self.page.expect_download(timeout=min(self.config.download_timeout_ms, 8_000)) as download_info:
                locator.click(force=True, timeout=3_000)
            return download_info.value
        except PlaywrightTimeoutError:
            return None
        except Exception:
            return None

    def _log_attachment_diagnostics(self, message: AttachmentMessage) -> None:
        script = """
        (index) => {
            const nodes = Array.from(document.querySelectorAll("div[data-testid='msg-container'], div.message-in, div.message-out"));
            const node = nodes[index];
            if (!node) return null;
            return Array.from(node.querySelectorAll("button, [role='button'], [aria-label], [title], [data-icon]"))
                .map(el => ({
                    tag: el.tagName,
                    text: (el.innerText || "").trim().slice(0, 80),
                    aria: el.getAttribute("aria-label"),
                    title: el.getAttribute("title"),
                    icon: el.getAttribute("data-icon")
                }))
                .slice(0, 50);
        }
        """
        try:
            details = self.page.evaluate(script, message.index)
            logger.info(
                "Diagnostico adjunto | contacto=%s archivo=%s index=%s detalles=%s",
                message.contact,
                message.suggested_name,
                message.index,
                details,
            )
        except Exception as exc:
            logger.info("No se pudo diagnosticar adjunto %s: %s", message.suggested_name, exc)

    @staticmethod
    def _extract_printer_key(previous_text: str) -> str | None:
        normalized_text = WhatsAppClient._normalize_keyword_text(previous_text)
        normalized_phrase = WhatsAppClient._normalize_keyword_text(DEFAULT_PRINT_PHRASE)
        if normalized_phrase in normalized_text:
            return "IMP"

        match = PRINTER_KEY_PATTERN.search(previous_text.upper())
        return match.group(1).upper() if match else None

    @staticmethod
    def _normalize_keyword_text(value: str) -> str:
        without_accents = unicodedata.normalize("NFKD", value)
        ascii_text = without_accents.encode("ascii", "ignore").decode("ascii")
        return re.sub(r"\s+", " ", ascii_text).strip().casefold()

    @staticmethod
    def _safe_filename(value: str) -> str:
        cleaned = SAFE_FILENAME_PATTERN.sub("_", value).strip(" ._")
        return cleaned[:120] or "archivo"

    @staticmethod
    def _unique_name(directory: Path, filename: str) -> Path:
        candidate = directory / filename
        if not candidate.exists():
            return candidate

        stem = candidate.stem
        suffix = candidate.suffix
        counter = 1
        while True:
            next_candidate = directory / f"{stem}_{counter}{suffix}"
            if not next_candidate.exists():
                return next_candidate
            counter += 1
