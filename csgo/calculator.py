import operator
import sys
from typing import List, Dict

from enum import Enum

from .collection import load_collections
from .condition import FloatRange, get_condition_range
from .contract import get_st_item_conversion_return, get_lf_item_conversion_return
from .price import STPriceManager, load_bck_prices, load_hexa_prices, load_lf_prices, LFPriceManager
from .type.contract import ContractReturn, ItemReturn
from .type.item import ItemRarity, Item
from .type.price import PriceTimeRange, STPrices, LFPrices


def pretty_print_items(items: Dict[str, float]):
    for item_name, item_price in items.items():
        print(f'\t - {item_name}: {item_price}')


class Model(Enum):
    HX = 'HX'
    BP = 'BP'
    LF = 'LF'

    @staticmethod
    def from_str(value: str):
        names = {
            'hx': Model.HX,
            'bp': Model.BP,
            'lf': Model.LF
        }

        return names.get(value)


collections = load_collections()
roi_list: List[ContractReturn] = []
returns: List[ItemReturn] = []

model = Model.from_str(sys.argv[1].lower()) if len(sys.argv) > 1 and sys.argv[1] else Model.LF
if not model:
    raise AssertionError(f'Could not determine model from string value \'{sys.argv[1]}\'')
else:
    print(f'Loading model {model.name}')

if model == Model.LF:
    prices: LFPrices = load_lf_prices()
    price_manager = LFPriceManager(prices)
else:
    prices: STPrices = load_hexa_prices() if model == Model.HX else load_bck_prices()
    price_manager = STPriceManager(prices, collections)

for col_name, collection in collections.items():
    for item in collection.items:
        if item.rarity < ItemRarity.COVERT:
            if model == Model.LF:
                required_available = 1
                returns += get_lf_item_conversion_return(item, collection, price_manager, required_available)
                stat_item = Item(item.name, item.rarity, item.collection_name, item.min_float, item.max_float, True)
                returns += get_lf_item_conversion_return(stat_item, collection, price_manager, required_available)
            else:
                time_range: PriceTimeRange = PriceTimeRange.DAYS_30
                returns += get_st_item_conversion_return(
                    item, collection, price_manager, time_range,
                    required_sold_amount=10, possible_price_discount=0.1, return_commission=0.09)
                stat_item = Item(item.name, item.rarity, item.collection_name, item.min_float, item.max_float, True)
                returns += get_st_item_conversion_return(
                    stat_item, collection, price_manager, time_range,
                    required_sold_amount=10, possible_price_discount=0.1, return_commission=0.15)

collection_name = None
for i in sorted(returns,
                key=operator.attrgetter('item.collection_name', 'item.rarity', 'item_condition',
                                        'item.full_name', 'item_revenue'),
                reverse=True):
    if i.item_roi >= 0 and i.item_revenue >= 0.7 and len(i.conversion_items) <= 30:
        if i.item.collection_name != collection_name:
            collection_name = i.item.collection_name
            print('\n' + collection_name)
        guaranteed = '(100%) ' if i.guaranteed else ''
        item_range = FloatRange(get_condition_range(i.item_condition).min_value, i.float_range.max_value)
        print(f'{guaranteed}[{i.item.rarity}] {i.float_range} '
              f'{i.item.full_name} ({str(i.item_condition)}) {i.item_buy_price * 10:.2f}: '
              f'{i.item_revenue * 10:.2f} ({i.item_roi * 100:.0f}%):')
        pretty_print_items(i.conversion_items)
