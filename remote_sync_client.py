import os
import json
import requests
from typing import Dict, Any, Optional, Tuple

class RemoteSyncClient:
    """
    Cliente para la comunicación y sincronización autenticada entre la app local
    de escritorio del organizador y el servidor web alojado en la nube (Render, Railway, VPS, etc.).
    """
    
    def __init__(self, config_path: Optional[str] = None):
        if config_path:
            self.config_path = config_path
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.config_path = os.path.join(base_dir, "remote_sync_config.json")
            
        self.remote_url = "https://subarashii-academy.onrender.com"
        self.api_key = "subarashii_secret_organizer_key_2026"
        self.enabled = True
        self.timeout = 8  # segundos
        
        self.load_config()

    def load_config(self):
        """Carga la configuración guardada de conexión con el hosting."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.remote_url = data.get("remote_url", self.remote_url).rstrip("/")
                    self.api_key = data.get("api_key", self.api_key).strip()
                    self.enabled = data.get("enabled", self.enabled)
            except Exception as e:
                print(f"[RemoteSyncClient] Error al leer configuración: {e}")

    def save_config(self, remote_url: str, api_key: str, enabled: bool):
        """Guarda la configuración de conexión."""
        self.remote_url = remote_url.strip().rstrip("/")
        self.api_key = api_key.strip()
        self.enabled = enabled
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump({
                    "remote_url": self.remote_url,
                    "api_key": self.api_key,
                    "enabled": self.enabled
                }, f, indent=2, ensure_ascii=False)
            return True, "Configuración guardada exitosamente."
        except Exception as e:
            return False, f"Error al guardar configuración: {e}"

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "TournamentOrganizerDesktop/2.0"
        }

    def test_connection(self) -> Tuple[bool, str]:
        """Prueba la conexión y credenciales con el servidor remoto."""
        if not self.remote_url:
            return False, "Debes ingresar una URL de servidor válida."
        try:
            url = f"{self.remote_url}/api/organizer/ping"
            resp = requests.get(url, headers=self._get_headers(), timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                msg = data.get("message", "Conexión autorizada y activa.")
                return True, f"¡Éxito! {msg}"
            elif resp.status_code == 401:
                return False, "Error 401: API Key incorrecta o no autorizada en el hosting."
            elif resp.status_code == 404:
                return False, "Error 404: Endpoint no encontrado. Verifica la URL del servidor."
            else:
                return False, f"Servidor respondió con código {resp.status_code}: {resp.text[:100]}"
        except requests.exceptions.ConnectionError:
            return False, f"No se pudo conectar al servidor en {self.remote_url}. ¿El servidor está encendido?"
        except requests.exceptions.Timeout:
            return False, "Tiempo de espera agotado al contactar al servidor (Timeout)."
        except Exception as e:
            return False, f"Error de conexión: {str(e)}"

    def sync_room_state(self, room_code: str, title: str, current_round: int, pairings: list, standings: list, timer_info: dict, status: str = "LOBBY") -> Tuple[bool, str]:
        """Envía el estado actual del torneo y sus rondas al servidor cloud."""
        if not self.enabled:
            return False, "Sincronización remota desactivada."
        try:
            url = f"{self.remote_url}/api/organizer/sync"
            payload = {
                "type": "room_sync",
                "room_code": room_code,
                "title": title,
                "current_round": current_round,
                "status": status,
                "pairings": pairings,
                "standings": standings,
                "timer": timer_info
            }
            resp = requests.post(url, json=payload, headers=self._get_headers(), timeout=self.timeout)
            if resp.status_code == 200:
                return True, "Sala sincronizada en la nube con éxito."
            return False, f"Fallo al sincronizar: {resp.status_code} {resp.text[:100]}"
        except Exception as e:
            return False, f"Error de red al sincronizar sala: {str(e)}"


    def fetch_room_events(self, room_code: str) -> Tuple[bool, Dict[str, Any]]:
        """Obtiene reportes y jugadores dropeados desde el servidor hosting."""
        if not self.enabled or not room_code:
            return False, {}
        try:
            url = f"{self.remote_url}/api/organizer/events/{room_code}"
            resp = requests.get(url, headers=self._get_headers(), timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                return True, data
            return False, {}
        except Exception:
            return False, {}

    def sync_full_snapshot(self, snapshot_content: dict, filename: Optional[str] = None) -> Tuple[bool, str]:
        """Sube un snapshot completo de la academia/ranking a la web remota."""
        if not self.enabled:
            return False, "Sincronización remota desactivada."
        try:
            url = f"{self.remote_url}/api/organizer/sync"
            payload = {
                "type": "full_snapshot",
                "snapshot": snapshot_content
            }
            if filename:
                payload["filename"] = filename
            resp = requests.post(url, json=payload, headers=self._get_headers(), timeout=12)
            if resp.status_code == 200:
                return True, "Snapshot general publicado en hosting con éxito."
            return False, f"Fallo al subir snapshot: {resp.status_code} {resp.text[:100]}"
        except Exception as e:
            return False, f"Error de red: {str(e)}"
