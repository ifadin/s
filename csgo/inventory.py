import base64
import json
import os
from typing import List

import requests
from requests import Response

from csgo.price import to_lf_price_entries
from csgo.type.float import get_float_value
from csgo.type.price import PriceEntry


class LFInventoryManager:
    inv_url = base64.b64decode('aHR0cHM6Ly9sb290LmZhcm0vZ2V0SW52X25ldy5waHA/Z2FtZT03MzA='.encode()).decode()
    rsv_url = base64.b64decode('aHR0cHM6Ly9sb290LmZhcm0vZ2V0UmVzZXJ2ZXMucGhw'.encode()).decode()
    inv_file = os.path.join('csgo', 'lf', 'lf_inv.json')
    rsv_file = os.path.join('csgo', 'lf', 'lf_rsv.json')

    def get_inventory(self) -> List[PriceEntry]:
        return self.get_owned_items() + self.get_reserved_items()

    @classmethod
    def get_owned_items(cls) -> List[PriceEntry]:
        return cls._load_items_from_file(cls.inv_file)

    @classmethod
    def get_reserved_items(cls) -> List[PriceEntry]:
        return cls._load_items_from_file(cls.rsv_file)

    @classmethod
    def _query_items(cls, url: str) -> Response:
        session_id = os.environ.get('LF_SESSION_ID')
        if not session_id:
            raise AssertionError('LF session id is required')
        res = requests.get(url, cookies={
            'PHPSESSID': session_id
        })
        res.raise_for_status()
        return res

    @classmethod
    def to_price_entries(cls, res: Response) -> List[PriceEntry]:
        return [i for items in to_lf_price_entries(res.json().get('result', {})).values() for i in items]

    @classmethod
    def _load_items_from_file(cls, file_path: str) -> List[PriceEntry]:
        with open(file_path) as f:
            data = json.loads(f.read())
            return [i for items in to_lf_price_entries(data.get('result', {})).values() for i in items]

    @classmethod
    def query_and_save(cls, url: str, file_path: str):
        items = cls._query_items(url).json()

        for item_id, item_details in items.get('result', {}).items():
            for i in item_details.get('u', []):
                i['f'] = get_float_value(i['id'], i['l'])
        with open(file_path, 'w') as f:
            f.write(json.dumps(items))


def update_lf():
    LFInventoryManager.query_and_save(LFInventoryManager.inv_url, LFInventoryManager.inv_file)