import base64
import itertools
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

    @classmethod
    def get_inventory(cls) -> List[PriceEntry]:
        return cls.get_owned_items() + cls.get_reserved_items()

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
        return [p for price_details in to_lf_price_entries(res.json().get('result', {})).values()
                for p in price_details.prices]

    @classmethod
    def _load_items_from_file(cls, file_path: str) -> List[PriceEntry]:
        with open(file_path) as f:
            data = json.loads(f.read())
            return [p for price_details in to_lf_price_entries(data.get('result', {})).values()
                    for p in price_details.prices]

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
    sls_url = base64.b64decode('aHR0cHM6Ly9hcGkuZG1hcmtldC5jb20vZXhjaGFuZ2UvdjEvdXNlci9vZmZlcnM/Z2FtZUlkPWE4'
                               'ZGImY3VycmVuY3k9VVNEJmxpbWl0PTEwMA=='.encode()).decode()
    inv_file = os.path.join('csgo', 'dm', 'dm_inv.yaml')
    sls_file = os.path.join('csgo', 'dm', 'dm_sls.yaml')

    def get_inventory(self, in_market: bool = None) -> List[PriceEntry]:
        own = self.get_own_inventory()
        on_sales = self.get_on_sales_inventory()
        if in_market is not None:
            return [i for i in itertools.chain(own, on_sales) if i.in_market == in_market]
        return own + on_sales

    def get_own_inventory(self) -> List[PriceEntry]:
        with open(self.inv_file) as f:
            data = yaml.load(f, Loader=yaml.SafeLoader)
            return [
                PriceEntry(item['t'], item['p'] * 1.2, item['f'],
                           item_id=item_id, item_name=item['n'], in_market=item.get('m'), withdrawable_in=item.get('w'))
                for item_id, item in data.get('inventory').items()
            ]

    def get_on_sales_inventory(self) -> List[PriceEntry]:
        with open(self.sls_file) as f:
            data = yaml.load(f, Loader=yaml.SafeLoader)
            return [
                PriceEntry(item['t'], item['p'] - 1, item['f'],
                           item_id=item_id, item_name=item['n'], in_market=item.get('m'), withdrawable_in=item.get('w'))
                for item_id, item in data.get('inventory').items()
            ]

    @classmethod
    def query_and_save(cls, url: str, file_path: str):
        items = {}
        for item in cls._query_items(url).json().get('objects', []):
            float_value = item['extra'].get('floatValue')
            inspect_link = item['extra'].get('inspectInGame')
            if not float_value and inspect_link:
                float_value = get_float_value_from_link(inspect_link)
            item_id = item['extra']['linkId']
            item_p = item.get('price').get('USD')
            item_price = cls.get_dm_item_sale_price(item['recommendedPrice']) if not item_p else float(item_p) / 100
            item_name = item['extra']['name']
            in_market = item.get('inMarket')
            t_lock = item['extra'].get('tradeLockDuration')
            withdrawable_in = int(t_lock / 3600) if t_lock else None
            if item_price and float_value:
                items[item_id] = {**{
                    'n': item_name, 'p': item_price, 'f': float_value, 't': item['title'], 'm': in_market
                }, **({'w': withdrawable_in} if withdrawable_in else {})}

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
    if not LFInventoryManager.get_owned_items():
        raise AssertionError('Own inventory is empty')


def update_dm():
    DMInventoryManager.query_and_save(DMInventoryManager.inv_url, DMInventoryManager.inv_file)
    DMInventoryManager.query_and_save(DMInventoryManager.sls_url, DMInventoryManager.sls_file)
