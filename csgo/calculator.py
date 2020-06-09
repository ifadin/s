import operator
import sys
from concurrent.futures.thread import ThreadPoolExecutor
from typing import List, Dict

from enum import Enum

from .bs.update import BSPrices
from .collection import load_collections
from .contract import BSContractCalc, STContractCalc, LFContractCalc, ContractCalc
from .conversion import FloatRange, get_condition_range, ConversionMap
from .price import STPriceManager, load_bck_prices, load_hexa_prices, load_lf_prices, LFPriceManager, load_bs_prices, \
    BSPriceManager, load_bs_sales
from .type.contract import ItemReturn
from .type.item import to_st_track, ItemRarity, Item
from .type.price import STPrices, LFPrices, PriceTimeRange


def pretty_print_items(items: Dict[str, float]):
    for item_name, item_price in items.items():
        print(f'\t - {item_name}: {item_price}')


class Model(Enum):
    BP = 'BP'
    BS = 'BS'
    HX = 'HX'
    LF = 'LF'

    @staticmethod
    def from_str(value: str):
        names = {
            'hx': Model.HX,
            'bp': Model.BP,
            'bs': Model.BS,
            'lf': Model.LF
        }

        return names.get(value.lower())


class GetItemReturns:
    def __init__(self, calc: ContractCalc, time_range):
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

if model == Model.LF:
    prices: LFPrices = load_lf_prices()
    price_manager = LFPriceManager(prices)
    calc = LFContractCalc(conversion_map, price_manager, required_available=1)
else:
    if model == Model.BS:
        prices: BSPrices = load_bs_prices()
        sales = load_bs_sales()
        price_manager = BSPriceManager(prices, sales)
        calc = BSContractCalc(conversion_map, price_manager)
    else:
        prices: STPrices = load_hexa_prices() if model == Model.HX else load_bck_prices()
        price_manager = STPriceManager(prices, collections)
        calc = STContractCalc(collections, price_manager,
                              required_sold_amount=10, possible_price_discount=0.1, return_commission=0.09)

returns: List[ItemReturn] = []
time_range: PriceTimeRange = PriceTimeRange.DAYS_30
items: List[Item] = []
for col_name, collection in collections.items():
    for item in collection.items:
        if item.rarity < ItemRarity.COVERT:
            items.append(item)
            items.append(to_st_track(item))

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
