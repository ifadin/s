import html
import json
import math
from abc import ABC, abstractmethod
from functools import reduce
from statistics import mean
from typing import Dict, Optional, List

import yaml

from csgo.bs.update import BSPrices, BSItemPrice, BSSalesHistory
from csgo.collection import get_next_level_items, get_prev_level_items
from csgo.type.item import Item, ItemCollection, ItemCondition, ItemRarity
from csgo.type.price import STPrices, PriceTimeRange, STItemPriceDetails, STItemPrice, \
    get_price_time_range_from_bck_string, \
    get_price_time_range_from_hexa_string, LFPrices, LFItemPrice, get_item_price_name

RarityConditionIncreasePriceRatios = Dict[ItemRarity, Dict[ItemCondition, float]]
RarityItemMap = Dict[ItemRarity, Optional[Item]]


class PriceManager(ABC):

    @abstractmethod
    def get_avg_price(self, item: Item,
                      item_condition: ItemCondition,
                      time_range: PriceTimeRange = PriceTimeRange.DAYS_30,
                      with_price_fallback: bool = True) -> Optional[float]:
        pass


class STPriceManager(PriceManager):

    def __init__(self,
                 prices: STPrices,
                 collections: Dict[str, ItemCollection]) -> None:
        self.prices = prices
        self.collections = collections
        self.condition_increase_ratios = self.calculate_condition_increase_price_ratios()

    def calculate_condition_increase_price_ratios(self,
                                                  time_range: PriceTimeRange = PriceTimeRange.DAYS_30) -> RarityConditionIncreasePriceRatios:
        conditions: List[ItemCondition] = list(ItemCondition)

        res: Dict[ItemRarity, Dict[ItemCondition, List[float]]] = {}
        for collection in self.collections.values():
            for item in collection.items:
                for condition in conditions[0:len(conditions) - 1]:
                    price = self.get_avg_price(item, condition, time_range)
                    if price:
                        next_condition_price = self.get_avg_price(item, ItemCondition(condition.value + 1), time_range)
                        if next_condition_price:
                            rarity = ItemRarity(item.rarity)
                            if rarity not in res:
                                res[rarity] = {}
                            if condition not in res[rarity]:
                                res[rarity][condition] = [price / next_condition_price]
                            else:
                                res[rarity][condition].append(price / next_condition_price)

        return {rarity: {cond: mean(ratios) for cond, ratios in res[rarity].items()} for rarity in res}

    def find_lowest_price_items(self, collection_name: str,
                                item_condition: ItemCondition,
                                price_time_range: PriceTimeRange = PriceTimeRange.DAYS_30) -> RarityItemMap:
        def find_lowest(rarity: ItemRarity) -> Optional[Item]:
            lowest_price_item: Optional[Item] = None
            lowest_price = math.inf
            for item in self.collections[collection_name].items:
                if item.rarity == rarity.value:
                    price = self.get_avg_price(item, item_condition, price_time_range)
                    if price and price < lowest_price:
                        lowest_price = price
                        lowest_price_item = item
            return lowest_price_item

        res = {}
        for r in ItemRarity:
            l = find_lowest(r)
            if l:
                res[r] = l
        return res

    def get_avg_price(self, item: Item,
                      item_condition: ItemCondition,
                      time_range: PriceTimeRange = PriceTimeRange.DAYS_30,
                      with_price_fallback: bool = True) -> Optional[float]:
        name = get_item_price_name(item.full_name, item_condition)
        p = self.prices.get(name)
        if p is not None:
            time_ranges = [t for t in PriceTimeRange if t >= time_range] if with_price_fallback else [time_range]
            for t_range in time_ranges:
                if t_range in p.prices and p.prices[t_range].average:
                    return p.prices[t_range].average

        return None

    def get_sold(self, item: Item,
                 item_condition: ItemCondition,
                 time_range: PriceTimeRange = PriceTimeRange.DAYS_30) -> Optional[int]:
        name = get_item_price_name(item.full_name, item_condition)
        p = self.prices.get(name)
        if p is not None:
            return int(p.prices[time_range].sold) if time_range in p.prices and p.prices[time_range].sold else None

        return None

    def get_std(self, item: Item,
                item_condition: ItemCondition,
                time_range: PriceTimeRange = PriceTimeRange.DAYS_30) -> Optional[float]:
        name = get_item_price_name(item.full_name, item_condition)
        p = self.prices.get(name)
        if p is not None:
            return p.prices[time_range].standard_deviation if time_range in p.prices else None

        return None

    def get_approx_price(self, item: Item,
                         item_condition: ItemCondition,
                         price_time_range: PriceTimeRange = PriceTimeRange.DAYS_30) -> Optional[float]:
        next_items = get_next_level_items(item, self.collections[item.collection_name])
        prev_items = get_prev_level_items(item, self.collections[item.collection_name])
        price_ratios: Dict[Item, List[float]] = {}

        for condition in ItemCondition:
            if condition != item_condition:
                item_price = self.get_avg_price(item, condition, price_time_range)
                if item_price:
                    for n_item in next_items:
                        n_item_price = self.get_avg_price(n_item, condition, price_time_range)
                        if n_item_price:
                            if n_item not in price_ratios:
                                price_ratios[n_item] = []
                            price_ratios[n_item].append(item_price / n_item_price)
                    for p_item in prev_items:
                        p_item_price = self.get_avg_price(p_item, condition, price_time_range)
                        if p_item_price:
                            if p_item not in price_ratios:
                                price_ratios[p_item] = []
                            price_ratios[p_item].append(item_price / p_item_price)

        item_approx_prices: List[float] = []
        for ref_item, ref_ratios in price_ratios.items():
            ref_item_price = self.get_avg_price(ref_item, item_condition, price_time_range)
            if ref_item_price:
                item_approx_prices.append(ref_item_price * mean(ref_ratios))
        return mean(item_approx_prices) if item_approx_prices else None

    def get_approx_price_from_rarity(self, item: Item, item_condition: ItemCondition,
                                     price_time_range: PriceTimeRange) -> Optional[float]:
        ratio = self.condition_increase_ratios[ItemRarity(item.rarity)]
        conditions: List[ItemCondition] = list(ItemCondition)
        cond_prices = {cond: self.get_avg_price(item, cond, price_time_range) for cond in conditions}

        left_prices = [cond for cond in conditions if cond < item_condition and cond_prices[cond]]
        left_ref_cond = left_prices[-1] if left_prices else None
        right_prices = [cond for cond in conditions if cond > item_condition and cond_prices[cond]]
        right_ref_cond = right_prices[-1] if right_prices else None

        approx_price_left: Optional[float] = None
        if left_ref_cond:
            for cond in conditions:
                if left_ref_cond <= cond < item_condition:
                    price = cond_prices[cond] if cond_prices[cond] else approx_price_left
                    approx_price_left = (price / ratio[cond]) if ratio.get(cond) and price else None

        approx_price_right: Optional[float] = None
        if right_ref_cond:
            for cond in conditions:
                if right_ref_cond >= cond > item_condition:
                    price = cond_prices[cond] if cond_prices[cond] else approx_price_right
                    approx_price_right = (price / ratio[cond]) if ratio.get(cond) and price else None

        return (mean(([approx_price_left] if approx_price_left else []) +
                     ([approx_price_right] if approx_price_right else []))
                if approx_price_left or approx_price_right else None)


class LFPriceManager(PriceManager):

    def __init__(self, prices: LFPrices) -> None:
        self.prices = prices

    def get_avg_price(self, item: Item, item_condition: ItemCondition,
                      time_range: PriceTimeRange = PriceTimeRange.DAYS_30,
                      with_price_fallback: bool = True) -> Optional[float]:
        item_name = get_item_price_name(item.full_name, item_condition)
        p = self.prices.get(item_name)
        return p.price if p else None

    def get_available(self, item: Item, item_condition: ItemCondition) -> Optional[int]:
        item_name = get_item_price_name(item.full_name, item_condition)
        p = self.prices.get(item_name)
        return p.tradable + p.reservable if p else None


class BSPriceManager(PriceManager):

    def __init__(self, prices: BSPrices, sales: BSSalesHistory) -> None:
        self.prices = prices
        self.sales = sales

    def get_avg_price(self, item: Item, item_condition: ItemCondition,
                      time_range: PriceTimeRange = PriceTimeRange.DAYS_30,
                      with_price_fallback: bool = True) -> Optional[float]:
        item_name = get_item_price_name(item, item_condition)
        sales_history = self.sales.get(item_name, [])

        return self.trim_mean(sales_history, 0.2) if sales_history else None

    def get_sale_prices(self, item: Item, item_condition: ItemCondition) -> List[BSItemPrice]:
        item_name = get_item_price_name(item.full_name, item_condition)
        return self.prices.get(item_name, [])

    @staticmethod
    def trim_mean(tlist, tperc) -> float:
        remove_n = int(math.floor(len(tlist) * tperc / 2))
        tlist.sort()
        if remove_n > 0:
            tlist = tlist[remove_n:-remove_n]
        return reduce(lambda a, b: a + b, tlist) / float(len(tlist))


def load_bck_prices() -> STPrices:
    def get_price_details(price: dict) -> STItemPriceDetails:
        return STItemPriceDetails(average=float(price['average']),
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
        for item_name_escaped, price_obj in res['items_list'].items():
            item_name = html.unescape(item_name_escaped)
            prices[item_name] = STItemPrice(item_name, {
                get_price_time_range_from_bck_string(price_key): get_price_details(price_details)
                for price_key, price_details in price_obj.get('price', {}).items()
                if get_price_time_range_from_bck_string(price_key)
            })

        return prices


def load_hexa_prices() -> STPrices:
    def get_price_details(price: dict) -> STItemPriceDetails:
        return STItemPriceDetails(average=float(price['avg']),
                                  sold=price.get('sales'),
                                  median=price['med'],
                                  standard_deviation=price.get('std'),
                                  lowest_price=price.get('min'),
                                  highest_price=price.get('max'))

    with open('csgo/hexa_prices.json') as f:
        res = json.loads(f.read())

        prices: STPrices = {}
        for item_name, price_obj in res['result']['prices'].items():
            prices[item_name] = STItemPrice(item_name, {
                get_price_time_range_from_hexa_string(price_key): get_price_details(price_details)
                for price_key, price_details in price_obj.items()
                if get_price_time_range_from_hexa_string(price_key)
            })

        return prices


def load_lf_prices() -> LFPrices:
    with open('csgo/lf_prices.json') as f:
        data = json.loads(f.read())

        prices: LFPrices = {}
        for price_obj in data:
            item_name = price_obj['name']
            prices[item_name] = LFItemPrice(item_name, price_obj['price'] / 100, price_obj['have'], price_obj['max'],
                                            price_obj['rate'] / 100, price_obj['tr'], price_obj['res'])

        return prices


def load_bs_prices() -> BSPrices:
    with open('csgo/bs/bs_prices.yaml') as f:
        data = yaml.load(f, Loader=yaml.SafeLoader)

        return {
            item_name: [BSItemPrice(item_name, float(price_value), float(float_value))
                        for float_value, price_value in price.items() if float_value and price_value]
            for item_name, price in data['prices'].items()
        }


def load_bs_sales() -> BSSalesHistory:
    with open('csgo/bs/bs_sales.yaml') as f:
        data = yaml.load(f, Loader=yaml.SafeLoader)

        return data['sales']
