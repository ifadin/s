import base64
import statistics
from time import sleep

import requests
from typing import List, NamedTuple, Tuple, Optional

from epics.auth import EAuth
from epics.domain import TemplateItem


class MarketItem(NamedTuple):
    template_id: int
    avg_sales: float
    offers: List[Tuple[int, int, int]]


class MarketTarget(NamedTuple):
    offer_id: int
    offer_value: int
    offer_score: int
    item: TemplateItem
    avg_sales: float

    @property
    def margin(self) -> Optional[float]:
        if not self.avg_sales or not self.offer_value:
            return None

        return (self.avg_sales - self.offer_value) / self.avg_sales

    @property
    def score_margin(self) -> Optional[float]:
        if not self.offer_value or not self.offer_score:
            return None

        return self.offer_value / self.offer_score / 10


class PriceService:
    buy_url = base64.b64decode('aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL21hcmtldC9idXk/Y2F0ZWdvcnlJZD0x'.encode()).decode()
    sales_url = base64.b64decode('aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL21hcmtldC9idXk/Y2F0ZWdvcnlJZD0xJnNvcnQ9'
                                 'cHJpY2U='.encode()).decode()
    sell_url = base64.b64decode(
        'aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL21hcmtldC9saXN0P2NhdGVnb3J5SWQ9MQ=='.encode()).decode()

    def __init__(self, auth: EAuth) -> None:
        self.auth = auth

    def buy_item(self, offer_id: int, offer_value: int) -> bool:
        r = requests.post(self.buy_url, auth=self.auth, json={'marketId': offer_id, 'price': offer_value})
        r.raise_for_status()
        return r.json()['success']

    def request_sales(self, target_id: int, entity_type: str, page: int = 1) -> dict:
        r = requests.get(f'{self.sales_url}&type={entity_type}&templateId={target_id}&page={page}', auth=self.auth)

        if r.status_code == 429:
            print(f'429: sleeping...')
            sleep(3)
            return self.request_sales(target_id, entity_type, page)

        r.raise_for_status()
        return r.json()

    def get_sales(self, item_id: int, entity_type: str, exhaustive: bool = False) -> MarketItem:
        def get_offers(res: dict):
            return [
                (o['marketId'], o['price'], o[entity_type]['rating'])
                for o in next(iter(res['data']['market']), [{}]) if o.get('marketId') and o.get('price')
            ]

        s = self.request_sales(item_id, entity_type)
        sample_size = 12
        avg_sales = self.trim_mean([
            e['price'] for e in s['data'].get('recentSales', [])[0:sample_size]
        ], 2, 2)

        offers = get_offers(s)
        page_num = 1
        next_page = s['data']['count'] == 40
        while exhaustive and next_page:
            page_num += 1
            s = self.request_sales(item_id, entity_type, page_num)
            offers += get_offers(s)
            next_page = s['data']['count'] == 40

        return MarketItem(item_id, avg_sales, offers)

    def get_trend(self, target_id: int, entity_type: str) -> Optional[Tuple[float, float, float, Optional[float]]]:
        s = self.request_sales(target_id, entity_type)
        offers = next(iter(s['data']['market']), [{}])
        min_offer = offers[0].get('price')
        if not min_offer:
            return None
        next_offer = offers[1].get('price') if len(offers) > 1 else None
        close_offers = sum((1 for o in offers[1:] if o.get('price') and o['price'] < min_offer * 1.15))

        sample_size = 12
        avg_sales = self.trim_mean([
            e['price'] for e in s['data'].get('recentSales', [])[0:sample_size]
        ], 2, 2)
        if not avg_sales:
            return None

        return min_offer, avg_sales, close_offers, next_offer

    def sell_item(self, item_id: int, price: int, entity_type: str) -> int:
        r = requests.post(self.sell_url, auth=self.auth, json={'price': price, 'id': item_id, 'type': entity_type})
        r.raise_for_status()
        return r.json()['data']['marketId']

    @staticmethod
    def trim_mean(tlist: list, ignore_min: int, ignore_max: int) -> Optional[float]:
        if not tlist:
            return None

        return (statistics.mean(tlist)
                if (ignore_min + ignore_max) >= len(tlist)
                else statistics.mean(sorted(tlist)[ignore_min:][:-ignore_max]))
