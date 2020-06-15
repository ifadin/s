import base64
import os
from typing import Dict, List, Optional, Set
from urllib import parse
from urllib.parse import urlparse, parse_qs

from requests import Response
from requests.auth import AuthBase

from csgo.conversion import ConversionMap
from csgo.interface.updater import Updater
from csgo.price import DMPriceManager, trim_mean, PriceManager
from csgo.type.item import ItemCollection
from csgo.type.price import PriceEntry


class DMUpdater(Updater):
    prices_file = os.path.join('csgo', 'dm', 'dm_prices.yaml')
    sales_file = os.path.join('csgo', 'dm', 'dm_sales.yaml')
    prices_url = base64.b64decode('aHR0cHM6Ly9hcGkuZG1hcmtldC5jb20vZXhjaGFuZ2UvdjEvbWFya2V0L2l0ZW1zP29yZGVyQnk9'
                                  'cHJpY2Umb3JkZXJEaXI9YXNjJmdhbWVJZD1hOGRiJmN1cnJlbmN5PVVTRA=='
                                  .encode()).decode()
    sales_url = base64.b64decode('aHR0cHM6Ly9hcGkuZG1hcmtldC5jb20vbWFya2V'
                                 '0cGxhY2UtYXBpL3YxL2xhc3Qtc2FsZXM/R2FtZUlEPWE4ZGImQ3VycmVuY3k9VVNE'
                                 .encode()).decode()

    def __init__(self, collections: Dict[str, ItemCollection], price_reference_delta: float = 1.3) -> None:
        super().__init__(collections, DMPriceManager().load(), price_reference_delta,
                         batch_size=12, price_page_size=100)

    @classmethod
    def get_items_for_price_update(cls, collections: Dict[str, ItemCollection], conversion_map: ConversionMap,
                                   price_manager: PriceManager, price_reference_delta: float) -> Dict[str, float]:
        return {
            i_name: ref_price for i_name, ref_price
            in super().get_items_for_price_update(collections, conversion_map, price_manager,
                                                  price_reference_delta).items()
            if 'Man-o' not in i_name
        }

    @classmethod
    def get_items_for_sale_update(cls, collections: Dict[str, ItemCollection]) -> Set[str]:
        return {i for i in super().get_items_for_sale_update(collections) if 'Man-o' not in i}

    @classmethod
    def get_item_prices_url(cls, market_name: str, ref_price: float, per_page: int) -> str:
        price_to = int(ref_price * 100) if ref_price else None
        return cls.prices_url + f'&title={market_name}&limit={per_page}' + (f'&priceTo={price_to}' if price_to else '')

    @classmethod
    def get_item_sales_url(cls, market_name: str) -> str:
        encoded_name = parse.quote(market_name).replace('\'', '%27')
        return cls.sales_url + f"&Title={encoded_name}"

    @classmethod
    def get_item_name_from_url(cls, url: str) -> str:
        q = parse_qs(urlparse(url).query)
        if 'Title' in q:
            return q['Title'][0]
        return q['title'][0]

    @classmethod
    def get_prices_from_response(cls, res: Response) -> List[PriceEntry]:
        prices = []
        item_name = cls.get_item_name_from_url(res.request.url)

        for o in res.json().get('objects', []):
            title = o.get('title')
            if title == item_name:
                price = o.get('price', {}).get('USD')
                float_value = o.get('extra', {}).get('floatValue')
                if float_value and price:
                    p = float(price) / 100
                    f = float(float_value)
                    link_id = o.get('extra', {}).get('linkId')
                    lock = o.get('extra', {}).get('tradeLockDuration')
                    w = int(lock / 3600) if lock else None
                    prices.append(PriceEntry(title, p, f, item_id=link_id, withdrawable_in=w))

        return prices

    @classmethod
    def get_page_number(cls, res: Response, per_page: int) -> int:
        q = parse_qs(urlparse(res.request.url).query)
        if q and 'offset' in q:
            o = q['offset'][-1]
            return int(int(o) / per_page) + 1
        return 1

    @classmethod
    def add_next_page_request(cls, res: Response, requests_queue, next_page: int, auth: AuthBase):
        requests_queue.append({
            'method': 'GET', 'url': res.request.url + f'&offset={100 * (next_page - 1)}', 'auth': auth
        })

    @classmethod
    def get_sale_price_from_response(cls, res: Response) -> Optional[float]:
        prices = [float(s['Price']['Amount']) / 100 for s in res.json().get('LastSales', [])[0:10]
                  if s.get('Price') and s['Price'].get('Amount')]
        return trim_mean(prices, 0.2) if prices else None
