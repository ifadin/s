import re
import time
from abc import ABC, abstractmethod
from typing import Dict, Set, List, Optional

import yaml
from requests import Response
from requests.auth import AuthBase
from requests_toolbelt import threaded
from tqdm import tqdm

from csgo.collection import get_next_level_items
from csgo.contract import get_conversion_items_return
from csgo.conversion import ConversionMap, get_item_possible_conditions
from csgo.price import PriceManager, load_item_sales, load_item_prices
from csgo.type.item import Item, ItemCondition, ItemCollection, ItemRarity, to_st_track
from csgo.type.price import get_market_name, ItemPrices, ItemSales, PriceEntry, SaleEntry, PriceDetails
from csgo.util import get_batches


def get_item_ref_prices(item: Item, conversion_map: ConversionMap, price_manager: PriceManager,
                        price_reference_delta: float = 1) -> Dict[ItemCondition, float]:
    ref_prices = {}
    conversion_rules = conversion_map.get_rules(item)
    for conversion_range, conversion_items in conversion_rules.items():
        item_condition = conversion_range.item_condition
        item_return = get_conversion_items_return(conversion_items, price_manager)
        if item_return:
            item_ref_price = item_return / 10 * price_reference_delta
            if item_ref_price > ref_prices.get(item_condition, 0):
                ref_prices[item_condition] = item_ref_price

    return ref_prices


class Updater(ABC):
    prices_file: str
    prices_url: str
    sales_file: str
    sales_url: str

    def __init__(self, collections: Dict[str, ItemCollection],
                 price_manager: PriceManager,
                 price_reference_delta: float = 1,
                 auth: AuthBase = None,
                 batch_size: int = None,
                 price_page_size: int = None):
        self.collections = collections
        self.conversion_map = ConversionMap(self.collections)
        self.price_manager = price_manager
        self.auth = auth
        self.price_reference_delta = price_reference_delta
        self.batch_size = batch_size
        self.price_page_size = price_page_size

    @classmethod
    def get_file_name(cls, item_name: str, file_type: str = 'json') -> str:
        n = re.sub('\\s\\|\\s', '_', item_name.lower())

        return re.sub("[-`'\\s]", '_', n) + f'.{file_type}'

    @classmethod
    def get_items_for_price_update(cls, collections: Dict[str, ItemCollection],
                                   conversion_map: ConversionMap,
                                   price_manager: PriceManager,
                                   price_reference_delta: float) -> Dict[str, float]:
        items = {}
        for collection in collections.values():
            for item in collection.items:
                if (ItemRarity.MIL_SPEC_GRADE <= item.rarity < ItemRarity.COVERT and
                        get_next_level_items(item, collection)):

                    for i in ([item, to_st_track(item)] if collection.st_track else [item]):
                        ref_prices = get_item_ref_prices(i, conversion_map, price_manager, price_reference_delta)
                        for item_condition in get_item_possible_conditions(i):
                            market_name = get_market_name(i, item_condition)
                            ref_price = ref_prices.get(item_condition)
                            items[market_name] = ref_price
        return items

    @classmethod
    def get_items_for_sale_update(cls, collections: Dict[str, ItemCollection]) -> Set[str]:
        items: Set[str] = set()
        for collection in collections.values():
            for item in collection.items:
                if item.rarity > ItemRarity.MIL_SPEC_GRADE:
                    for i in ([item, to_st_track(item)] if collection.st_track else [item]):
                        for item_condition in get_item_possible_conditions(i):
                            market_name = get_market_name(i, item_condition)
                            items.add(market_name)
        return items

    @classmethod
    @abstractmethod
    def get_item_name_from_url(cls, url: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def get_item_prices_url(cls, market_name: str, ref_price: float, per_page: int) -> str:
        pass

    @classmethod
    @abstractmethod
    def get_item_sales_url(cls, market_name: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def get_prices_from_response(cls, res: Response) -> List[PriceEntry]:
        pass

    @classmethod
    @abstractmethod
    def get_sale_price_from_response(cls, res: Response) -> Optional[float]:
        pass

    @classmethod
    @abstractmethod
    def add_next_page_request(cls, res: Response, requests_queue, next_page: int, auth: AuthBase):
        pass

    def request_prices(self, items: Dict[str, float]) -> ItemPrices:
        prices = {}
        processing_requests = [{
            'method': 'GET',
            'url': self.get_item_prices_url(item_name, ref_price, per_page=self.price_page_size),
            'auth': self.auth
        } for item_name, ref_price in items.items()]

        for requests_batch in get_batches(processing_requests, self.batch_size):
            while requests_batch:
                additional_requests = []
                rate_limited = False

                responses_generator, exceptions_generator = threaded.map(requests_batch, num_processes=6)
                for res in responses_generator:
                    rate_limited = self.user_rate_limit_strategy(res, additional_requests, self.auth, rate_limited)

                    success = self.check_request(res, additional_requests, self.auth)
                    if success:
                        item_name = self.get_item_name_from_url(res.request.url)
                        items = self.get_prices_from_response(res)
                        self.update_price_map(prices, items, item_name)

                        page = self.get_page_number(res, self.price_page_size)
                        tqdm.write(f' - Updated {item_name} with {len(items)} items - '
                                   f'{page} ({res.elapsed.seconds}s)')

                        if page and len(items) == self.price_page_size:
                            next_page = page + 1
                            tqdm.write(f'   Scheduling page {next_page} for {item_name}')
                            self.add_next_page_request(res, additional_requests, next_page, self.auth)

                for exc in exceptions_generator:
                    tqdm.write(f'[ERROR] {exc}')
                if additional_requests:
                    tqdm.write(f'Rescheduled {len(additional_requests)} requests')
                requests_batch = additional_requests

        return prices

    @classmethod
    @abstractmethod
    def get_page_number(cls, res: Response, per_page: int) -> int:
        pass

    def request_sales(self, items: Set[str]) -> ItemSales:
        sales = {}
        processing_requests = [{
            'method': 'GET', 'url': self.get_item_sales_url(market_name), 'auth': self.auth
        } for market_name in items]

        for requests_batch in get_batches(processing_requests, self.batch_size):
            while requests_batch:
                additional_requests = []

                rate_limited = False
                responses_generator, exceptions_generator = threaded.map(requests_batch, num_processes=6)
                for res in responses_generator:
                    if self.user_rate_limit_strategy(res, additional_requests, self.auth, rate_limited):
                        rate_limited = True

                    success = self.check_request(res, additional_requests, self.auth)
                    if success:
                        sale_price = self.get_sale_price_from_response(res)
                        item_name = self.get_item_name_from_url(res.request.url)
                        updated = int(time.time())
                        sales[item_name] = SaleEntry(item_name, sale_price, updated)
                        tqdm.write(f'Updated {item_name} with {sale_price} ({res.elapsed.seconds}s)')

                for exc in exceptions_generator:
                    tqdm.write(f'[ERROR] {exc.exception}')

                if additional_requests:
                    tqdm.write(f'Rescheduled {len(additional_requests)} requests')
                requests_batch = additional_requests

        return sales

    @classmethod
    def user_rate_limit_strategy(cls, res: Response, requests_queue, auth: AuthBase,
                                 rate_limited: bool = False) -> bool:
        if res.status_code == 429:
            requests_queue.append({'method': 'GET', 'url': res.request.url, 'auth': auth})
            if not rate_limited:
                time.sleep(3)
                return True
        return False

    @classmethod
    def check_request(cls, res: Response, requests_queue, auth: AuthBase) -> bool:
        if res.status_code >= 500:
            requests_queue.append({'method': 'GET', 'url': res.request.url, 'auth': auth})
            return False
        if res.status_code == 429:
            return False
        else:
            res.raise_for_status()
            cls.check_api_status(res)

        return True

    @classmethod
    def check_api_status(cls, res: Response):
        body = res.json()
        if not body or (body.get('status') and body['status'] != 'success'):
            raise AssertionError(f'Request was unsuccessful: {body}')

    @classmethod
    def save_prices(cls, prices: ItemPrices, file_name: str):
        with open(file_name, 'w') as f:
            yaml.dump({'items': {
                item_name: {
                    'u': price_details.updated_at,
                    'prices': {
                        p.item_id: {
                            **{'f': p.float_value, 'p': p.price},
                            **({'w': p.withdrawable_in} if p.withdrawable_in else {})
                        } for p in price_details.prices}}
                for item_name, price_details in prices.items()
            }}, f, default_flow_style=False)

    @classmethod
    def save_sales(cls, sales: ItemSales, file_name: str):
        with open(file_name, 'w') as f:
            yaml.dump({'sales': {
                s.item_name: {**{'u': s.updated_at}, **({'p': s.price} if s.price else {})}
                for item_name, s in sales.items()
            }}, f, default_flow_style=False)

    def update_prices(self, cache_expiration_hours: int = 2):
        start = time.time()

        item_prices = load_item_prices(self.prices_file)
        update_threshold = int(time.time()) - cache_expiration_hours * 60 * 60

        items_for_update = {
            item_name: ref_price
            for item_name, ref_price in self.get_items_for_price_update(
                self.collections, self.conversion_map, self.price_manager, self.price_reference_delta).items()
            if item_name not in item_prices or item_prices[item_name].updated_at < update_threshold
        }

        print(f'Updating {len(items_for_update)} items price information...')
        prices = item_prices
        with tqdm(total=len(items_for_update)) as pbar:
            for items_batch in get_batches(list(items_for_update.items()), 100):
                items = dict(items_batch)
                new_prices = self.request_prices(items)
                prices = {**prices, **new_prices}
                self.save_prices(prices, self.prices_file)
                pbar.update(len(new_prices))

        end = time.time()
        print(f'Finished in {end - start:2f}s')

    def update_sales(self, cache_expiration_hours: int = 24):
        start = time.time()

        item_sales = load_item_sales(self.sales_file)
        update_threshold = int(time.time()) - cache_expiration_hours * 60 * 60
        items_for_update = {
            i for i in self.get_items_for_sale_update(self.collections)
            if i not in item_sales or item_sales[i].updated_at < update_threshold
        }

        print(f'Updating {len(items_for_update)} items sales information...')
        sales = item_sales
        with tqdm(total=len(items_for_update)) as pbar:
            for items_batch in get_batches(list(items_for_update), 100):
                items = set(items_batch)
                new_sales = self.request_sales(items)
                sales = {**sales, **new_sales}
                self.save_sales(sales, self.sales_file)
                pbar.update(len(new_sales))

        end = time.time()
        print(f'Finished in {end - start:2f}s')

    @classmethod
    def update_price_map(cls, price_map: ItemPrices, prices: List[PriceEntry], item_name: str):
        u_time = int(time.time())
        if item_name not in price_map:
            price_map[item_name] = PriceDetails([], u_time)
        for p in prices:
            i_name = p.market_hash_name
            if i_name not in price_map:
                price_map[i_name] = PriceDetails([], u_time)
            price_map[i_name] = PriceDetails(price_map[i_name].prices + [p], u_time)
