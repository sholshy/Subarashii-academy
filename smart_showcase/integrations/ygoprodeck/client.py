import requests
from typing import List, Optional
from integrations.base import BaseCatalogProvider, CatalogCardData

class YGOPRODeckClient(BaseCatalogProvider):
    BASE_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def _parse_card(self, item: dict) -> CatalogCardData:
        image_url = None
        if item.get('card_images') and len(item['card_images']) > 0:
            image_url = item['card_images'][0].get('image_url')

        return CatalogCardData(
            ygoprodeck_id=item.get('id'),
            name=item.get('name', ''),
            card_type=item.get('type', ''),
            description=item.get('desc', ''),
            race=item.get('race', ''),
            attribute=item.get('attribute'),
            atk=item.get('atk'),
            def_points=item.get('def'),
            level=item.get('level'),
            scale=item.get('scale'),
            link_val=item.get('linkval'),
            archetype=item.get('archetype'),
            card_sets=item.get('card_sets', []),
            image_url=image_url
        )

    def search_by_name(self, name: str) -> List[CatalogCardData]:
        try:
            resp = requests.get(self.BASE_URL, params={'fname': name}, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json().get('data', [])
                return [self._parse_card(c) for c in data]
        except Exception as e:
            # Documented error handling / logging
            print(f"[YGOPRODeckClient] Error buscando carta por nombre: {e}")
        return []

    def get_by_id(self, card_id: int) -> Optional[CatalogCardData]:
        try:
            resp = requests.get(self.BASE_URL, params={'id': card_id}, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json().get('data', [])
                if data:
                    return self._parse_card(data[0])
        except Exception as e:
            print(f"[YGOPRODeckClient] Error obteniendo carta por id: {e}")
        return None

    def search_by_set_code(self, set_code: str) -> List[CatalogCardData]:
        try:
            resp = requests.get(self.BASE_URL, params={'cardset': set_code}, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json().get('data', [])
                return [self._parse_card(c) for c in data]
        except Exception as e:
            print(f"[YGOPRODeckClient] Error buscando por set: {e}")
        return []
