import base64
import os
import time
from typing import List, Dict, Optional
from urllib.parse import urlparse, parse_qs

from requests import Response, Request
from requests.auth import AuthBase

from csgo.bs.token import TokenProvider
from csgo.interface.updater import Updater
from csgo.price import BSPriceManager, trim_mean
from csgo.type.item import ItemCollection
from csgo.type.price import PriceEntry


class BSAuth(AuthBase):

    def __init__(self, token_provider: TokenProvider) -> None:
        self.token_provider = token_provider

    def __call__(self, r: Request):
        api_key = self.token_provider.get_api_key()
        token = self.token_provider.get_token()
        r.url = r.url + f'&api_key={api_key}&code={token}'
        return r


class BSUpdater(Updater):
    prices_url = base64.b64decode(
        'aHR0cHM6Ly9iaXRza2lucy5jb20vYXBpL3YxL2dldF9pbnZlbnRvcnlfb25fc2FsZQ=='.encode()).decode()
    sales_url = base64.b64decode('aHR0cHM6Ly9iaXRza2lucy5jb20vYXBpL3YxL2dldF9zYWxlc19pbmZv'.encode()).decode()
    prices_file = os.path.join('csgo', 'bs', 'bs_prices.yaml')
    sales_file = os.path.join('csgo', 'bs', 'bs_sales.yaml')

    def __init__(self, collections: Dict[str, ItemCollection],
                 price_reference_delta: float = 1.3, token_provider=TokenProvider()) -> None:
        self.token_provider = token_provider
        super().__init__(collections, BSPriceManager().load(), price_reference_delta,
                         auth=BSAuth(self.token_provider), price_page_size=480)
        self.collections = collections

    @classmethod
    def get_item_prices_url(cls, market_name: str, ref_price: float,
                            page: int = 1, per_page=480) -> str:
        max_price = f'{ref_price:.2f}' if ref_price else ''
        return (f'{cls.prices_url}/?app_id=730&market_hash_name={market_name}'
                f'&is_souvenir=-1&max_price={max_price}&sort_by=price&order=asc'
                f'&page={page}&per_page={per_page}')

    @classmethod
    def get_item_sales_url(cls, market_name: str) -> str:
        return f'{cls.sales_url}/?app_id=730&market_hash_name={market_name}'

    @classmethod
    def get_item_name_from_url(cls, url: str) -> str:
        return parse_qs(urlparse(url).query)['market_hash_name'][0]

    @classmethod
    def get_prices_from_response(cls, res: Response) -> List[PriceEntry]:
        def get_withdrawable_at(value: int) -> Optional[int]:
            if not value:
                return None
            diff = value - int(time.time())
            return None if diff <= 0 else int(diff / 3600)

        return [PriceEntry(i['market_hash_name'], float(i['price']), float(i['float_value']),
                           item_id=i['item_id'], withdrawable_in=get_withdrawable_at(i.get('withdrawable_at')))
                for i in res.json().get('data', {}).get('items', []) if i.get('price') and i.get('float_value')]

    @classmethod
    def get_page_number(cls, res: Response, per_page: int) -> int:
        return res.json().get('data', {}).get('page')

    @classmethod
    def add_next_page_request(cls, res: Response, requests_queue, next_page: int, auth: AuthBase):
        requests_queue.append({
            'method': 'GET', 'url': res.request.url + f'&page={next_page}', 'auth': auth
        })

    @classmethod
    def get_sale_price_from_response(cls, res: Response) -> Optional[float]:
        prices = [float(s['price']) for s in res.json()['data'].get('sales', []) if s.get('price')]
        return trim_mean(prices, 0.2) if prices else None
