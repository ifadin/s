import json
from typing import Dict, List

import yaml

from csgo.type.item import Item, ItemCollection
from csgo.type.paintkit import PaintKit
from csgo.type.price import STPrices, \
    ItemPrice, ItemPriceDetails, get_price_time_range_from_bck_string, get_price_time_range_from_hexa_string


def load_collections() -> Dict[str, ItemCollection]:
    with open('csgo/collections.yaml') as f:
        res = yaml.load(f, Loader=yaml.SafeLoader)
        return {
            col_name: ItemCollection(col_name, [
                Item(item_name, item_details['rarity'], col_name)
                for item_name, item_details
                in col_details['items'].items()])
            for col_name, col_details
            in res['collections'].items()
        }


def load_bck_prices() -> STPrices:
    def get_price_details(price: dict) -> ItemPriceDetails:
        return ItemPriceDetails(average=float(price['average']),
                                sold=price['sold'],
                                median=price.get('median'),
                                standard_deviation=(float(price.get('standard_deviation'))
                                                    if price.get('standard_deviation') else None),
                                lowest_price=price.get('lowest_price'),
                                highest_price=price.get('highest_price'))

    with open('csgo/bck_prices.json') as f:
        res = json.loads(f.read())
        if not res.get('success'):
            raise AssertionError('Prices response was not successful')

        prices: STPrices = {}
        for item_name, price_obj in res['items_list'].items():
            prices[item_name] = ItemPrice(item_name, {
                get_price_time_range_from_bck_string(price_key): get_price_details(price_details)
                for price_key, price_details in price_obj.get('price', {}).items()
                if get_price_time_range_from_bck_string(price_key)
            })

        return prices


def load_hexa_prices() -> STPrices:
    def get_price_details(price: dict) -> ItemPriceDetails:
        return ItemPriceDetails(average=float(price['avg']),
                                sold=price.get('sales'),
                                median=price['med'],
                                standard_deviation=price.get('std'),
                                lowest_price=price.get('min'),
                                highest_price=price.get('max'))

    with open('csgo/hexa_prices.json') as f:
        res = json.loads(f.read())

        prices: STPrices = {}
        for item_name, price_obj in res['result']['prices'].items():
            prices[item_name] = ItemPrice(item_name, {
                get_price_time_range_from_hexa_string(price_key): get_price_details(price_details)
                for price_key, price_details in price_obj.items()
                if get_price_time_range_from_hexa_string(price_key)
            })

        return prices


def load_paintkits() -> List[PaintKit]:
    with open('csgo/paintkits.json') as f:
        res = json.loads(f.read())
        return [PaintKit(p['id'], p['tag'], p['minFloat'], p['maxFloat']) for p in res]
