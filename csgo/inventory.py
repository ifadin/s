import base64
import json
import os
from abc import ABC, abstractmethod
from statistics import mean
from typing import List, Optional

import requests
import yaml
from requests import Response

from csgo.price import to_lf_price_entries
from csgo.type.float import get_float_value, get_float_value_from_link
from csgo.type.price import PriceEntry


class InventoryManager(ABC):

    @abstractmethod
    def get_inventory(self) -> List[PriceEntry]:
        pass


class LFInventoryManager(InventoryManager):
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
                if i.get('l') and i.get('id'):
                    i['f'] = get_float_value(i['id'], i['l'])
        with open(file_path, 'w') as f:
            f.write(json.dumps(items))


class DMInventoryManager(InventoryManager):
    inv_url = base64.b64decode('aHR0cHM6Ly9hcGkuZG1hcmtldC5jb20vZXhjaGFuZ2UvdjEvdXN'
                               'lci9pdGVtcz9nYW1lSWQ9YThkYiZsaW1pdD0xMDAmY3VycmVuY3k9VVNE'.encode()).decode()
    inv_file = os.path.join('csgo', 'dm', 'dm_inv.yaml')

    def get_inventory(self) -> List[PriceEntry]:
        with open(self.inv_file) as f:
            data = yaml.load(f, Loader=yaml.SafeLoader)
            return [PriceEntry(item['title'], item['price'], item['float_value'],
                               item_id=item_id, item_name=item['name'])
                    for item_id, item in data.get('inventory').items()]

    @classmethod
    def query_and_save(cls, url: str, file_path: str):
        items = {}
        for item in cls._query_items(url).json().get('objects', []):
            if item['inMarket']:
                float_value = item['extra'].get('floatValue')
                inspect_link = item['extra'].get('inspectInGame')
                if not float_value and inspect_link:
                    float_value = get_float_value_from_link(inspect_link)
                item_id = item['extra']['linkId']
                item_price = cls.get_dm_item_sale_price(item['recommendedPrice'])
                item_name = item['extra']['name']
                if item_price and float_value:
                    items[item_id] = {
                        'name': item_name, 'price': item_price, 'float_value': float_value, 'title': item['title']
                    }

        with open(file_path, 'w') as f:
            yaml.dump({'inventory': items}, f, default_flow_style=False)

    @staticmethod
    def get_dm_item_sale_price(p: dict) -> Optional[float]:
        ref_prices = []
        d3 = p.get('d3', {}).get('USD')
        d7 = p.get('d7', {}).get('USD')
        d7p = p.get('d7plus', {}).get('USD')
        ref_prices += [float(d3) / 100] if d3 else []
        ref_prices += [float(d7) / 100] if d7 else []
        ref_prices += [float(d7p) / 100] if d7p else []

        return mean(ref_prices) if ref_prices else None

    @classmethod
    def _query_items(cls, url: str) -> Response:
        token = os.environ.get('DM_AUTH_TOKEN')
        if not token:
            raise AssertionError('DM auth token is required')
        res = requests.get(url, headers={
            'authorization': token
        })
        res.raise_for_status()
        return res


def update_lf():
    LFInventoryManager.query_and_save(LFInventoryManager.inv_url, LFInventoryManager.inv_file)


def update_dm():
    DMInventoryManager.query_and_save(DMInventoryManager.inv_url, DMInventoryManager.inv_file)
