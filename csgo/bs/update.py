import html
import time
from operator import attrgetter
from typing import NamedTuple, Dict, List

import requests
import yaml
from requests import Response

from csgo.bs.token import TokenProvider
from csgo.type.item import ItemCondition


class BSItemPrice(NamedTuple):
    market_hash_name: str
    price: float
    float_value: float
    item_rarity: str = None


BSPriceMap = Dict[str, List[BSItemPrice]]


def get_inventory(query: str, api_key: str, token: str,
                  page: int = 1, per_page=480) -> Response:
    res = requests.get(f'https://bitskins.com/api/v1/get_inventory_on_sale/?api_key={api_key}&'
                       f'app_id=730&market_hash_name={query}&code={token}&'
                       f'is_souvenir=-1&'
                       f'page={page}&per_page={per_page}')
    res.raise_for_status()
    check_api_status(res)

    return res


def update_price_map(price_map: BSPriceMap, prices: List[BSItemPrice]):
    for p in prices:
        item_name = p.market_hash_name
        if item_name not in price_map:
            price_map[item_name] = []
        price_map[item_name] += [p]


def get_prices_from_response(res: Response) -> List[BSItemPrice]:
    return [BSItemPrice(i['market_hash_name'], i['price'], i['float_value'], i['item_rarity'])
            for i in res.json().get('data', {}).get('items', [])]


def get_item_prices(item_type: str, item_condition: ItemCondition, token_provider: TokenProvider,
                    per_page=480) -> BSPriceMap:
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


def check_api_status(res: Response):
    body = res.json()
    if not body or body.get('status') != 'success':
        raise AssertionError(f'Request was unsuccessful: {body}')


def save_prices(prices_map: BSPriceMap):
    with open('csgo/bs/bs_prices.yaml', 'w') as f:
        yaml.dump({'prices': {
            item_name: {p.float_value: p.price for p in item_prices}
            for item_name, item_prices in prices_map.items()
        }}, f, default_flow_style=False)


def update_bs_prices():
    token_provider = TokenProvider()
    item_types = [
        'AK-47', 'AUG', 'AWP',
        'CZ75-Auto', 'Desert Eagle', 'Dual Berettas', 'FAMAS', 'Five-SeveN', 'G3SG1', 'Galil AR',
        'Glock-18', 'M249', 'M4A1-S', 'M4A4', 'MAC-10', 'MAG-7', 'MP5-SD', 'MP7', 'MP9', 'Negev', 'Nova', 'P2000',
        'P250', 'P90', 'PP-Bizon', 'R8 Revolver', 'SCAR-20', 'SG 553', 'SSG 08', 'Sawed-Off', 'Tec-9', 'UMP-45',
        'USP-S', 'XM1014'
    ]
    last_tier_sample_limit = 8
    price_map: BSPriceMap = {}
    for t in item_types:
        for i in ItemCondition:
            print(f'Updating {t} ({str(i)}) ', end='')
            start = time.time()

            prices = {
                item_name: (item_prices
                            if item_prices and item_prices[0].item_rarity.lower() != 'covert'
                            else sorted(item_prices, key=attrgetter('price'))[0:last_tier_sample_limit])
                for item_name, item_prices in get_item_prices(t, i, token_provider).items()
            }
            price_map = {**price_map, **prices}
            end = time.time()
            print(f'({(end - start):.2f}s)')

    save_prices(price_map)
