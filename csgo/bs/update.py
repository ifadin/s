import html
import time
from concurrent.futures.thread import ThreadPoolExecutor
from typing import NamedTuple, Dict, List, Tuple

import requests
import yaml
from requests import Response

from csgo.bs.token import TokenProvider
from csgo.collection import load_collections
from csgo.type.item import ItemCondition, to_st_track
from csgo.type.price import get_item_price_name


class BSItemPrice(NamedTuple):
    market_hash_name: str
    price: float
    float_value: float
    item_rarity: str = None


BSPrices = Dict[str, List[BSItemPrice]]
BSSalesHistory = Dict[str, List[float]]


class GetInventoryOnSaleTask:
    def __init__(self, token_provider: TokenProvider):
        self.token_provider = token_provider

    def __call__(self, item_details: Tuple[str, ItemCondition]) -> BSPrices:
        item_type, item_condition = item_details
        start = time.time()

        prices = {
            item_name: item_prices
            for item_name, item_prices in get_item_prices(item_type, item_condition, self.token_provider).items()
            if item_prices and item_prices[0].item_rarity.lower() != 'covert'
        }
        end = time.time()
        print(f'Updated {item_type} ({str(item_condition)}) in {(end - start):.2f}s')
        return prices


class GetSalesHistoryTask:
    def __init__(self, token_provider: TokenProvider):
        self.token_provider = token_provider

    def __call__(self, item_name: str) -> Tuple[str, List[float]]:
        print(f'Updating {item_name}')

        sales = get_item_price_history(item_name, self.token_provider)
        return item_name, sales[0:10]


def get_inventory(query: str, api_key: str, token: str,
                  page: int = 1, per_page=480) -> Response:
    res = requests.get(f'https://bitskins.com/api/v1/get_inventory_on_sale/?api_key={api_key}&'
                       f'app_id=730&market_hash_name={query}&code={token}&'
                       f'is_souvenir=-1&'
                       f'page={page}&per_page={per_page}')
    if res.status_code == 429:
        time.sleep(3)
        return get_inventory(query, api_key, token, page, per_page)
    else:
        res.raise_for_status()
        check_api_status(res)

    return res


def get_history(market_hash_name: str, api_key: str, token: str) -> Response:
    res = requests.get(f'https://bitskins.com/api/v1/get_sales_info/?api_key={api_key}&code={token}&app_id=730'
                       f'&market_hash_name={html.escape(market_hash_name)}')
    if res.status_code == 429:
        time.sleep(3)
        return get_history(market_hash_name, api_key, token)
    else:
        res.raise_for_status()
        check_api_status(res)

    return res


def update_price_map(price_map: BSPrices, prices: List[BSItemPrice]):
    for p in prices:
        item_name = p.market_hash_name
        if item_name not in price_map:
            price_map[item_name] = []
        price_map[item_name] += [p]


def get_prices_from_response(res: Response) -> List[BSItemPrice]:
    return [BSItemPrice(i['market_hash_name'], i['price'], i['float_value'], i['item_rarity'])
            for i in res.json().get('data', {}).get('items', [])]


def get_item_prices(item_type: str, item_condition: ItemCondition, token_provider: TokenProvider,
                    per_page=480) -> BSPrices:
    token = token_provider.get_token()
    api_key = token_provider.get_api_key()

    query = html.escape(f'{item_type} ({str(item_condition)})')
    page = 1
    prices = {}

    items = get_prices_from_response(get_inventory(query, api_key, token, page, per_page))
    update_price_map(prices, items)
    while len(items) == per_page:
        page += 1
        items = get_prices_from_response(get_inventory(query, api_key, token, page, per_page))
        update_price_map(prices, items)

    return prices


def get_item_price_history(item_name: str, token_provider: TokenProvider) -> List[float]:
    token = token_provider.get_token()
    api_key = token_provider.get_api_key()

    res = get_history(item_name, api_key, token).json()

    return [float(s['price']) for s in res['data'].get('sales', []) if s.get('price')]


def check_api_status(res: Response):
    body = res.json()
    if not body or body.get('status') != 'success':
        raise AssertionError(f'Request was unsuccessful: {body}')


def save_prices(prices_map: BSPrices):
    with open('csgo/bs/bs_prices.yaml', 'w') as f:
        yaml.dump({'prices': {
            item_name: {p.float_value: p.price for p in item_prices}
            for item_name, item_prices in prices_map.items()
        }}, f, default_flow_style=False)


def save_sales_history(sales_history: BSSalesHistory):
    with open('csgo/bs/bs_sales.yaml', 'w') as f:
        yaml.dump({'sales': sales_history}, f, width=200)


def update_bs_prices():
    token_provider = TokenProvider()
    item_types = [
        'AK-47', 'AUG', 'AWP',
        'CZ75-Auto', 'Desert Eagle', 'Dual Berettas', 'FAMAS', 'Five-SeveN', 'G3SG1', 'Galil AR',
        'Glock-18', 'M249', 'M4A1-S', 'M4A4', 'MAC-10', 'MAG-7', 'MP5-SD', 'MP7', 'MP9', 'Negev', 'Nova', 'P2000',
        'P250', 'P90', 'PP-Bizon', 'R8 Revolver', 'SCAR-20', 'SG 553', 'SSG 08', 'Sawed-Off', 'Tec-9', 'UMP-45',
        'USP-S', 'XM1014'
    ]
    items: List[Tuple[str, ItemCondition]] = [(t, i) for i in ItemCondition for t in item_types]

    print(f'Updating {len(item_types)} item types...')
    with ThreadPoolExecutor(max_workers=5) as executor:
        price_map: BSPrices = {}
        for p in executor.map(GetInventoryOnSaleTask(token_provider), items, chunksize=5):
            price_map = {**price_map, **p}
        save_prices(price_map)


def update_bs_sales_history():
    token_provider = TokenProvider()
    items: List[str] = []
    for col_name, collection in load_collections().items():
        for item in collection.items:
            st_item = to_st_track(item)
            for i in [item, st_item]:
                for item_condition in ItemCondition:
                    item_name = get_item_price_name(i, item_condition)
                    items.append(item_name)

    with ThreadPoolExecutor(max_workers=5) as executor:
        sales_history: BSSalesHistory = dict(executor.map(GetSalesHistoryTask(token_provider), items, chunksize=5))
        save_sales_history(sales_history)
