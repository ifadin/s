import base64
import html
import os
import re
import time
from abc import ABC, abstractmethod
from concurrent.futures.thread import ThreadPoolExecutor
from statistics import mean
from typing import Dict, Tuple, List

import requests
import yaml
from requests import Response

from csgo.collection import load_collections, get_next_level_items
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
    DMPrices = Dict[str, Dict[float, float]]
    prices_url = base64.b64decode('aHR0cHM6Ly9hcGkuZG1hcmtldC5jb20vZXhjaGFuZ2UvdjEvbWFya2V0L2l0ZW1zP29yZGVyQnk9'
                                  'cHJpY2Umb3JkZXJEaXI9YXNjJmdhbWVJZD1hOGRiJmxpbWl0PTEwMCZjdXJyZW5jeT1VU0Q='
                                  .encode()).decode()
    sales_url = base64.b64decode('aHR0cHM6Ly9hcGkuZG1hcmtldC5jb20vZXhjaGFuZ2UvdjEvbWFya2V0L3JlY29tbWVuZC1wcmljZS9hOGRi'
                                 .encode()).decode()
    prices_file = os.path.join('csgo', 'dm', 'dm_prices.yaml')
    sales_file = os.path.join('csgo', 'dm', 'dm_sales.yaml')

    def __init__(self, collections: Dict[str, ItemCollection]) -> None:
        self.collections = collections

    def get_items_for_prices(self) -> List[str]:
        items: List[str] = []
        for collection in self.collections.values():
            for item in collection.items:
                if (ItemRarity.MIL_SPEC_GRADE <= item.rarity < ItemRarity.COVERT and
                        get_next_level_items(item, collection)):
                    for i in ([item, to_st_track(item)] if collection.st_track else [item]):
                        for item_condition in get_item_possible_conditions(i):
                            market_name = get_market_name(i, item_condition)
                            items.append(market_name)
        return items

    def get_items_for_sales(self) -> List[str]:
        items: List[str] = []
        for collection in self.collections.values():
            for item in collection.items:
                if item.rarity > ItemRarity.MIL_SPEC_GRADE:
                    for i in ([item, to_st_track(item)] if collection.st_track else [item]):
                        for item_condition in get_item_possible_conditions(i):
                            market_name = get_market_name(i, item_condition)
                            items.append(market_name)
        return items

    def request_prices(self, items: List[str]) -> DMPrices:
        with ThreadPoolExecutor(max_workers=2) as executor:
            return dict(((item_name, item_price) for item_name, item_price
                         in executor.map(DMGetPricesTask(self), items, chunksize=5) if item_price))

    def request_sales(self, items: List[str]) -> ItemSales:
        with ThreadPoolExecutor(max_workers=1) as executor:
            return dict(((item_name, item_price) for item_name, item_price
                         in executor.map(DMGetSalesTask(self), items, chunksize=10) if item_price))

    @classmethod
    def request_price(cls, url: str, market_name: str) -> Response:
        res = requests.get(url + ('' if '?' in url else '?') + f'&title={html.escape(market_name)}')
        res.raise_for_status()
        return res

    @classmethod
    def save_prices(cls, prices: DMPrices, file_name: str):
        with open(file_name, 'w') as f:
            yaml.dump({'prices': prices}, f, default_flow_style=False)

    @classmethod
    def save_sales(cls, sales: ItemSales, file_name: str):
        with open(file_name, 'w') as f:
            yaml.dump({'sales': sales}, f, default_flow_style=False)

    def update_prices(self):
        items_for_prices = self.get_items_for_prices()
        print(f'Updating {len(items_for_prices)} items prices information...')
        prices = self.request_prices(items_for_prices)
        self.save_prices(prices, self.prices_file)

    def update_sales(self):
        items_for_sales = self.get_items_for_sales()
        print(f'Updating {len(items_for_sales)} items sales information...')
        sales = self.request_sales(items_for_sales)
        self.save_sales(sales, self.sales_file)


class DMGetPricesTask:
    def __init__(self, updater: DMUpdater):
        self.updater = updater

    def __call__(self, market_name: str, attempt=0) -> Tuple[str, Dict[float, float]]:
        print(f'Updating {market_name}' + (f' ({attempt})' if attempt else ''))
        try:
            prices = {}
            # TODO; next pages
            for o in self.updater.request_price(self.updater.prices_url, market_name).json().get('objects', []):
                title = o.get('title')
                if title == market_name:
                    price = o.get('price', {}).get('USD')
                    float_value = o.get('extra', {}).get('floatValue')
                    if float_value and price:
                        p = float(price) / 100
                        f = float(float_value)
                        prices[f] = p

            return market_name, prices
        except Exception as e:
            if attempt > 5:
                raise e
            print(e)
            time.sleep(3)
            return self(market_name, attempt + 1)


class DMGetSalesTask:
    def __init__(self, updater: DMUpdater):
        self.updater = updater

    def __call__(self, market_name: str, attempt=0) -> Tuple[str, float]:
        print(f'Updating {market_name}' + (f' ({attempt})' if attempt else ''))
        try:
            p = self.updater.request_price(self.updater.sales_url, market_name).json()
            ref_prices = []
            d3 = p.get('d3', {}).get('amount')
            d7 = p.get('d7', {}).get('amount')
            d7p = p.get('d7plus', {}).get('amount')
            ref_prices += [float(d3) / 100] if d3 else []
            ref_prices += [float(d7) / 100] if d7 else []
            ref_prices += [float(d7p) / 100] if d7p else []

            price = mean(ref_prices) if ref_prices else None
            return market_name, price
        except Exception as e:
            if attempt > 5:
                raise e
            print(e)
            time.sleep(3)
            return self(market_name, attempt + 1)


def update_dm_prices():
    collections = load_collections()
    updater = DMUpdater(collections)
    updater.update_prices()


def update_dm_sales():
    collections = load_collections()
    updater = DMUpdater(collections)
    updater.update_sales()
