import unicodedata
import re
import os
import sys

def get_resource_path(relative_path):
    """Obtiene la ruta absoluta al recurso, funciona en dev y en PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_appdata_dir():
    """Obtiene la ruta a AppData para guardar base de datos y caché con permisos"""
    appdata = os.getenv('APPDATA')
    if appdata:
        path = os.path.join(appdata, "YGO_Tools")
    else:
        path = os.path.join(os.path.expanduser("~"), ".ygo_tools")
    os.makedirs(path, exist_ok=True)
    return path

def normalize_player_name(name: str) -> str:
    """
    Normalizes a player name to ensure robust matching.
    - Removes leading/trailing spaces
    - Replaces multiple spaces with a single space
    - Converts to lowercase
    - Removes diacritics (accents, etc)
    """
    if not name:
        return ""
    
    # Trim and normalize spaces
    name = name.strip()
    name = re.sub(r'\s+', ' ', name)
    
    # Lowercase
    name = name.lower()
    
    # Remove accents
    name = ''.join(c for c in unicodedata.normalize('NFD', name)
                  if unicodedata.category(c) != 'Mn')
    
    return name

def format_iso_to_local_time(iso_str: str) -> str:
    """Convierte una cadena de fecha/hora ISO (típicamente UTC) a hora local en formato 24h (HH:MM)."""
    if not iso_str:
        return "-"
    try:
        s = str(iso_str).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        elif not ("+" in s or "-" in s[10:]):
            s = s + "+00:00"
        from datetime import datetime
        dt = datetime.fromisoformat(s)
        dt_local = dt.astimezone()
        return dt_local.strftime("%H:%M")
    except Exception:
        if "T" in str(iso_str):
            return str(iso_str).split("T")[1][:5]
        return str(iso_str)[:5]

