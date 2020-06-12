import base64
import html
import os
import re
from abc import ABC, abstractmethod
from concurrent.futures.thread import ThreadPoolExecutor
from statistics import mean
from typing import Dict, Tuple, List

import requests
import yaml
from requests import Response

from csgo.collection import load_collections
from csgo.conversion import get_item_possible_conditions
from csgo.type.item import ItemCollection, ItemRarity, to_st_track
from csgo.type.price import get_market_name, ItemSales


class Updater(ABC):

    @abstractmethod
    def update_sales(self):
        pass

    @classmethod
    def get_file_name(cls, item_name: str, file_type: str = 'json') -> str:
        n = re.sub('\\s\\|\\s', '_', item_name.lower())

        return re.sub("[-`'\\s]", '_', n) + f'.{file_type}'


class DMUpdater(Updater):
    sales_url = base64.b64decode('aHR0cHM6Ly9hcGkuZG1hcmtldC5jb20vZXhjaGFuZ2UvdjEvbWFya2V0L3JlY29tbWVuZC1wcmljZS9hOGRi'
                                 .encode()).decode()
    sales_file = os.path.join('csgo', 'dm', 'dm_sales.yaml')

    def __init__(self, collections: Dict[str, ItemCollection]) -> None:
        self.collections = collections

    def update_sales(self):
        items_for_sales = self.get_items_for_sales()
        print(f'Updating {len(items_for_sales)} items sales information...')
        sales = self.request_sales(items_for_sales)
        self.save_sales(sales, self.sales_file)

    def get_items_for_sales(self) -> List[str]:
        items: List[str] = []
        for collection in self.collections.values():
            for item in collection.items:
                if item.rarity > ItemRarity.MIL_SPEC_GRADE:
                    for i in [item, to_st_track(item)]:
                        for item_condition in get_item_possible_conditions(i):
                            market_name = get_market_name(i, item_condition)
                            items.append(market_name)
        return items

    def request_sales(self, items: List[str]) -> ItemSales:
        with ThreadPoolExecutor(max_workers=5) as executor:
            return dict(((item_name, item_price) for item_name, item_price
                         in executor.map(DMGetSalesTask(self), items, chunksize=5) if item_price))

    @classmethod
    def request_sale_price(cls, market_name: str) -> Response:
        res = requests.get(cls.sales_url + f'?&title={html.escape(market_name)}')
        res.raise_for_status()
        return res

    @classmethod
    def save_sales(cls, sales: ItemSales, file_name: str):
        with open(file_name, 'w') as f:
            yaml.dump({'sales': sales}, f, default_flow_style=False)


class DMGetSalesTask:
    def __init__(self, updater: DMUpdater):
        self.updater = updater

    def __call__(self, market_name: str) -> Tuple[str, float]:
        print(f'Updating {market_name}')

        p = self.updater.request_sale_price(market_name).json()
        ref_prices = []
        d3 = p.get('d3', {}).get('amount')
        d7 = p.get('d7', {}).get('amount')
        d7p = p.get('d7plus', {}).get('amount')
        ref_prices += [float(d3) / 100] if d3 else []
        ref_prices += [float(d7) / 100] if d7 else []
        ref_prices += [float(d7p) / 100] if d7p else []

        price = mean(ref_prices) if ref_prices else None
        return market_name, price


def update_dm():
    collections = load_collections()
    updater = DMUpdater(collections)
    updater.update_sales()
