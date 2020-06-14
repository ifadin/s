import base64
import html
import os
import time
from concurrent.futures.thread import ThreadPoolExecutor
from statistics import mean
from typing import Dict, Tuple, List, NamedTuple

import requests
from requests import Response

from csgo.interface.updater import Updater
from csgo.price import DMPriceManager
from csgo.type.item import ItemCollection
from csgo.type.price import ItemSales


class DMItemPrice(NamedTuple):
    item_id: str
    item_float: float
    item_price: float


class DMUpdater(Updater):
    DMPrices = Dict[str, List[DMItemPrice]]
    prices_url = base64.b64decode('aHR0cHM6Ly9hcGkuZG1hcmtldC5jb20vZXhjaGFuZ2UvdjEvbWFya2V0L2l0ZW1zP29yZGVyQnk9'
                                  'cHJpY2Umb3JkZXJEaXI9YXNjJmdhbWVJZD1hOGRiJmxpbWl0PTEwMCZjdXJyZW5jeT1VU0Q='
                                  .encode()).decode()
    sales_url = base64.b64decode('aHR0cHM6Ly9hcGkuZG1hcmtldC5jb20vZXhjaGFuZ2UvdjEvbWFya2V0L3JlY29tbWVuZC1wcmljZS9hOGRi'
                                 .encode()).decode()
    prices_file = os.path.join('csgo', 'dm', 'dm_prices.yaml')
    sales_file = os.path.join('csgo', 'dm', 'dm_sales.yaml')

    def __init__(self, collections: Dict[str, ItemCollection], relaxation_delta: float = 1.3) -> None:
        super().__init__(collections, DMPriceManager().load(), relaxation_delta)

    def request_prices(self, items: Dict[str, float]) -> DMPrices:
        with ThreadPoolExecutor(max_workers=1) as executor:
            return dict(((item_name, item_prices) for item_name, item_prices
                         in executor.map(DMGetPricesTask(self), items.items(), chunksize=10) if item_prices))

    def request_sales(self, items: List[str]) -> ItemSales:
        with ThreadPoolExecutor(max_workers=1) as executor:
            return dict(((item_name, item_price) for item_name, item_price
                         in executor.map(DMGetSalesTask(self), items, chunksize=10) if item_price))

    @classmethod
    def request_price(cls, url: str, market_name: str) -> Response:
        res = requests.get(url + ('' if '?' in url else '?') + f'&title={html.escape(market_name)}')
        res.raise_for_status()
        return res


class DMGetPricesTask:
    def __init__(self, updater: DMUpdater):
        self.updater = updater

    def __call__(self, item_details: Tuple[str, float], attempt=0) -> Tuple[str, List[DMItemPrice]]:
        market_name, ref_price = item_details
        ref_price_str = f'{ref_price:.2f}' if ref_price else 'None'
        print(f'Updating {market_name} - {ref_price_str}' + (f' ({attempt})' if attempt else ''))
        try:
            prices = []
            price_to = int(ref_price * 100) if ref_price else None
            url = self.updater.prices_url + (f'&priceTo={price_to}' if price_to else '')
            res = self.updater.request_price(url, market_name).json()
            total = res.get('total', {}).get('items')
            pages_amount = int(int(total) / 100) if total else 0
            pages_objects = [
                self.updater.request_price(url + f'&offset={100 * (i + 1)}', market_name).json().get('objects', [])
                for i in range(0, pages_amount)
            ]
            for objects in [res.get('objects', [])] + pages_objects:
                for o in objects:
                    title = o.get('title')
                    if title == market_name:
                        price = o.get('price', {}).get('USD')
                        float_value = o.get('extra', {}).get('floatValue')
                        if float_value and price:
                            p = float(price) / 100
                            f = float(float_value)
                            link_id = o.get('extra', {}).get('linkId')
                            prices.append(DMItemPrice(link_id, f, p))

            return market_name, prices
        except Exception as e:
            if attempt > 5:
                raise e
            print(e)
            time.sleep(3)
            return self(item_details, attempt + 1)


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
