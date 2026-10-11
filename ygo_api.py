import os
import json
import requests
from threading import Thread

CACHE_DIR = "cache"
DB_DIR = os.path.join(CACHE_DIR, "db")
IMG_SMALL_DIR = os.path.join(CACHE_DIR, "images_small")
IMG_LARGE_DIR = os.path.join(CACHE_DIR, "images_large")

os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(IMG_SMALL_DIR, exist_ok=True)
os.makedirs(IMG_LARGE_DIR, exist_ok=True)

class YgoApi:
    @staticmethod
    def fetch_database(format_name, callback=None):
        """Fetches the card database for a format if not cached, returns a list of card dicts."""
        filename = os.path.join(DB_DIR, f"{format_name.lower()}_cards.json")
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if callback:
                        callback(data)
                    return data
            except Exception:
                pass

        def _download():
            try:
                url = f"https://db.ygoprodeck.com/api/v7/cardinfo.php?format={format_name.lower()}"
                res = requests.get(url, timeout=10)
                res.raise_for_status()
                data = res.json().get("data", [])
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f)
                if callback:
                    callback(data)
            except Exception as e:
                print(f"Error fetching {format_name} DB: {e}")
                if callback:
                    callback([])
        
        Thread(target=_download, daemon=True).start()
        return None # indicating it's loading async

    @staticmethod
    def get_image_path(card_id, image_url, size="small", callback=None):
        """Returns the local path to the image, downloading it async if needed."""
        target_dir = IMG_SMALL_DIR if size == "small" else IMG_LARGE_DIR
        path = os.path.join(target_dir, f"{card_id}.jpg")
        
        if os.path.exists(path):
            if callback:
                callback(path)
            return path
            
        def _download():
            try:
                res = requests.get(image_url, timeout=10)
                if res.status_code == 200:
                    with open(path, 'wb') as f:
                        f.write(res.content)
                    if callback:
                        callback(path)
            except Exception as e:
                print(f"Error downloading image {card_id}: {e}")
                
        Thread(target=_download, daemon=True).start()
        return None
