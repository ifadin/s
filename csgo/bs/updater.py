import base64
import os
import time
from typing import List, Dict, Set, Optional
from urllib.parse import urlparse, parse_qs

from requests import Response, PreparedRequest, Request
from requests.auth import AuthBase
from requests_toolbelt import threaded
from tqdm import tqdm

from csgo.bs.token import TokenProvider
from csgo.interface.updater import Updater
from csgo.price import BSPriceManager, trim_mean
from csgo.type.item import ItemCollection
from csgo.type.price import PriceEntry, ItemPrices, ItemSales


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
                 relaxation_delta: float = 1.3, token_provider=TokenProvider()) -> None:
        super().__init__(collections, BSPriceManager().load(), relaxation_delta)
        self.token_provider = token_provider
        self.collections = collections

    def request_prices(self, items: Dict[str, float], per_page: int = 480) -> ItemPrices:
        prices = {}
        auth = BSAuth(self.token_provider)
        processing_requests = [{
            'method': 'GET',
            'url': self.request_inventory_on_sale(item_name, ref_price, per_page=per_page),
            'auth': auth
        } for item_name, ref_price in items.items() if item_name.lower()[0] in {'m'}]

        with tqdm(total=len(processing_requests)) as pbar:
            while processing_requests:
                tqdm.write(f'Got batch of {len(processing_requests)} request(s) to process')
                additional_requests = []
                rate_limited = False

                responses_generator, exceptions_generator = threaded.map(processing_requests)
                for res in responses_generator:
                    if not rate_limited and res.status_code == 429:
                        time.sleep(3)
                        rate_limited = True

                    success = self.check_request(res, additional_requests, auth)
                    if success:
                        original_req: PreparedRequest = res.request
                        items = self.get_prices_from_response(res)
                        if items:
                            self.update_price_map(prices, items)

                        page = res.json().get('data', {}).get('page')
                        item_name = parse_qs(urlparse(original_req.url).query)['market_hash_name'][0]
                        tqdm.write(f' - Updated {item_name} with {len(items)} items - '
                                   f'{page} ({res.elapsed.seconds}s)')

                        if page and len(items) == per_page:
                            next_page = page + 1
                            tqdm.write(f'   Scheduling page {next_page} for {item_name}')
                            self.add_next_page_request(res, additional_requests, next_page, auth)
                        else:
                            pbar.update(1)

                for exc in exceptions_generator:
                    print(f'ERROR : {exc}')

                processing_requests = additional_requests

        return prices

    def request_sales(self, items: Set[str]) -> ItemSales:
        sales = {}
        auth = BSAuth(self.token_provider)
        processing_requests = [{
            'method': 'GET', 'url': self.request_price_history(market_name), 'auth': auth
        } for market_name in items]

        with tqdm(total=len(processing_requests)) as pbar:
            while processing_requests:
                tqdm.write(f'Got batch of {len(processing_requests)} request(s) to process')
                additional_requests = []
                rate_limited = False

                responses_generator, exceptions_generator = threaded.map(processing_requests)
                for res in responses_generator:
                    if not rate_limited and res.status_code == 429:
                        time.sleep(3)
                        rate_limited = True

                    success = self.check_request(res, additional_requests, auth)
                    if success:
                        original_req: PreparedRequest = res.request
                        sale_price = self.get_sale_price_from_response(res)
                        item_name = parse_qs(urlparse(original_req.url).query)['market_hash_name'][0]
                        if sale_price:
                            sales[item_name] = sale_price
                            pbar.update(1)
                        tqdm.write(f'Updated {item_name} with {sale_price} ({res.elapsed.seconds}s)')

                for exc in exceptions_generator:
                    print(f'ERROR : {exc}')

                processing_requests = additional_requests

        return sales

    @classmethod
    def check_request(cls, res: Response, requests_queue, auth: AuthBase):
        if res.status_code in [429, 401]:
            item_name = parse_qs(urlparse(res.request.url).query)['market_hash_name'][0]
            tqdm.write(f'[WARN] rescheduling {item_name}')

            requests_queue.append({'method': 'GET', 'url': res.request.url, 'auth': auth})
            return False
        else:
            res.raise_for_status()
            cls.check_api_status(res)

        return True

    @classmethod
    def add_next_page_request(cls, res: Response, requests_queue, next_page: int, auth: AuthBase):
        requests_queue.append({
            'method': 'GET', 'url': res.request.url + f'&page={next_page}', 'auth': auth
        })

    @classmethod
    def request_inventory_on_sale(cls, market_name: str, ref_price: float,
                                  page: int = 1, per_page=480) -> str:
        max_price = f'{ref_price:.2f}' if ref_price else ''
        return (f'{cls.prices_url}/?app_id=730&market_hash_name={market_name}'
                f'&is_souvenir=-1&max_price={max_price}&sort_by=price&order=asc'
                f'&page={page}&per_page={per_page}')

    @classmethod
    def request_price_history(cls, market_name: str) -> str:
        return f'{cls.sales_url}/?app_id=730&market_hash_name={market_name}'

    @classmethod
    def check_api_status(cls, res: Response):
        body = res.json()
        if not body or body.get('status') != 'success':
            raise AssertionError(f'Request was unsuccessful: {body}')

    @classmethod
    def get_prices_from_response(cls, res: Response) -> List[PriceEntry]:
        return [PriceEntry(i['market_hash_name'], float(i['price']), float(i['float_value']), item_id=i['item_id'])
                for i in res.json().get('data', {}).get('items', []) if i.get('price') and i.get('float_value')]

    @classmethod
    def get_sale_price_from_response(cls, res: Response) -> Optional[float]:
        prices = [float(s['price']) for s in res.json()['data'].get('sales', []) if s.get('price')]
        return trim_mean(prices, 0.2) if prices else None

    @classmethod
    def update_price_map(cls, price_map: ItemPrices, prices: List[PriceEntry]):
        for p in prices:
            item_name = p.market_hash_name
            if item_name not in price_map:
                price_map[item_name] = []
            price_map[item_name] += [p]
