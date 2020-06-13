import operator
import sys
from concurrent.futures.thread import ThreadPoolExecutor
from typing import List, Dict

from enum import Enum

from .collection import load_collections, get_next_level_items
from .contract import BSItemReturnCalc, STItemReturnCalc, LFItemReturnCalc, ItemReturnCalc, DMItemReturnCalc
from .conversion import get_condition_range, ConversionMap
from .price import LFPriceManager, BSPriceManager, BCKPriceManager, HXPriceManager, DMPriceManager
from .type.contract import ItemReturn
from .type.float import FloatRange
from .type.item import to_st_track, ItemRarity, Item
from .type.price import PriceTimeRange


def pretty_print_items(items: Dict[str, float]):
    for item_name, item_price in items.items():
        print(f'\t - {item_name}: {item_price}')


class Model(Enum):
    BCK = 'BCK'
    BS = 'BS'
    DM = 'DM'
    HX = 'HX'
    LF = 'LF'

    @staticmethod
    def from_str(value: str):
        names = {
            'bck': Model.BCK,
            'bs': Model.BS,
            'dm': Model.DM,
            'hx': Model.HX,
            'lf': Model.LF
        }

        return names.get(value.lower())


class GetItemReturns:
    def __init__(self, calc: ItemReturnCalc, time_range):
        self.calc = calc
        self.time_range = time_range

    def __call__(self, item: Item) -> List[ItemReturn]:
        return self.calc.get_item_returns(item, self.time_range)


model = Model.from_str(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] else Model.LF
if not model:
    raise AssertionError(f'Could not determine model from string value \'{sys.argv[1]}\'')
else:
    print(f'Loading model {model.name}')

collections = load_collections()
conversion_map = ConversionMap(collections)

if model == Model.BS:
    price_manager = BSPriceManager().load()
    calc = BSItemReturnCalc(conversion_map, price_manager)
if model == Model.DM:
    price_manager = DMPriceManager().load()
    calc = DMItemReturnCalc(conversion_map, price_manager)
if model == Model.LF:
    price_manager = LFPriceManager().load()
    calc = LFItemReturnCalc(conversion_map, price_manager)
if model == Model.BCK:
    price_manager = BCKPriceManager(collections).load()
    calc = STItemReturnCalc(collections, price_manager,
                            required_sold_amount=10, possible_price_discount=0.1, return_commission=0.09)
if model == Model.HX:
    price_manager = HXPriceManager(collections).load()
    calc = STItemReturnCalc(collections, price_manager,
                            required_sold_amount=10, possible_price_discount=0.1, return_commission=0.09)

returns: List[ItemReturn] = []
time_range: PriceTimeRange = PriceTimeRange.DAYS_30
items: List[Item] = []
for col_name, collection in collections.items():
    for item in collection.items:
        if item.rarity < ItemRarity.COVERT and get_next_level_items(item, collection):
            items.append(item)
            if collection.st_track:
                items.append(to_st_track(item))
print(f'{len(items)} items to process')

with ThreadPoolExecutor(max_workers=10) as executor:
    returns = list((r for res in executor.map(GetItemReturns(calc, time_range), items, chunksize=10) for r in res))

for i in sorted(returns,
                key=operator.attrgetter('item.rarity', 'float_range.min_value', 'float_range.max_value',
                                        'item_revenue'),
                reverse=False):
    if i.item_revenue > 1 and len(i.output_items) <= 30:
        guaranteed = '(100%) ' if i.guaranteed else ''
        item_range = FloatRange(get_condition_range(i.item_condition).min_value, i.float_range.max_value)
        print(f'{guaranteed}[{i.item.rarity}] {i.item_float} {i.float_range} '
              f'{i.item.full_name} ({str(i.item_condition)}) {i.item_investment:.2f}: '
              f'{i.item_revenue:.2f} ({i.item_roi * 100:.0f}%):')
        pretty_print_items(i.output_items)
