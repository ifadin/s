import re
import time
from abc import ABC, abstractmethod
from typing import Dict, Set

import yaml

from csgo.collection import get_next_level_items
from csgo.contract import get_conversion_items_return
from csgo.conversion import ConversionMap, get_item_possible_conditions
from csgo.price import PriceManager
from csgo.type.item import Item, ItemCondition, ItemCollection, ItemRarity, to_st_track
from csgo.type.price import get_market_name, ItemPrices, ItemSales


def get_item_ref_prices(item: Item, conversion_map: ConversionMap, price_manager: PriceManager,
                        relaxation_delta: float = 1) -> Dict[ItemCondition, float]:
    ref_prices = {}
    conversion_rules = conversion_map.get_rules(item)
    for conversion_range, conversion_items in conversion_rules.items():
        item_condition = conversion_range.item_condition
        item_return = get_conversion_items_return(conversion_items, price_manager)
        if item_return:
            item_ref_price = item_return / 10 * relaxation_delta
            if item_ref_price > ref_prices.get(item_condition, 0):
                ref_prices[item_condition] = item_ref_price

    return ref_prices


class Updater(ABC):
    prices_file: str
    sales_file: str

    def __init__(self, collections: Dict[str, ItemCollection], price_manager: PriceManager,
                 relaxation_delta: float = 1):
        self.collections = collections
        self.conversion_map = ConversionMap(self.collections)
        self.price_manager = price_manager
        self.relaxation_delta = relaxation_delta

    @classmethod
    def get_file_name(cls, item_name: str, file_type: str = 'json') -> str:
        n = re.sub('\\s\\|\\s', '_', item_name.lower())

        return re.sub("[-`'\\s]", '_', n) + f'.{file_type}'

    @classmethod
    def get_items_for_price_update(cls, collections: Dict[str, ItemCollection],
                                   conversion_map: ConversionMap,
                                   price_manager: PriceManager,
                                   relaxation_delta: float) -> Dict[str, float]:
        items = {}
        for collection in collections.values():
            for item in collection.items:
                if (ItemRarity.MIL_SPEC_GRADE <= item.rarity < ItemRarity.COVERT and
                        get_next_level_items(item, collection)):
                    for i in ([item, to_st_track(item)] if collection.st_track else [item]):
                        ref_prices = get_item_ref_prices(i, conversion_map, price_manager, relaxation_delta)
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

    @abstractmethod
    def request_prices(self, items: Dict[str, float]) -> ItemPrices:
        pass

    @abstractmethod
    def request_sales(self, items: Set[str]) -> ItemSales:
        pass

    @classmethod
    def save_prices(cls, prices: ItemPrices, file_name: str):
        with open(file_name, 'w') as f:
            yaml.dump({'prices': {
                item_name: {p.item_id: {p.float_value: p.price} for p in item_prices}
                for item_name, item_prices in prices.items()
            }}, f, default_flow_style=False)

    @classmethod
    def save_sales(cls, sales: ItemSales, file_name: str):
        with open(file_name, 'w') as f:
            yaml.dump({'sales': sales}, f, default_flow_style=False)

    def update_prices(self):
        start = time.time()

        items_for_prices = self.get_items_for_price_update(
            self.collections, self.conversion_map, self.price_manager, self.relaxation_delta)
        print(f'Updating {len(items_for_prices)} items price information...')
        prices = self.request_prices(items_for_prices)
        print(f'Found {sum([len(p) for p in prices.values()])} prices for {len(prices)} items')
        self.save_prices(prices, self.prices_file)
        end = time.time()
        print(f'Finished in {end - start:2f}s')

    def update_sales(self):
        start = time.time()

        items_for_sales = self.get_items_for_sale_update(self.collections)
        print(f'Updating {len(items_for_sales)} items sales information...')
        sales = self.request_sales(items_for_sales)
        self.save_sales(sales, self.sales_file)
        end = time.time()
        print(f'Finished in {end - start:2f}s')
