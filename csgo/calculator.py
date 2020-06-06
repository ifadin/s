import operator
import sys
from typing import List, Dict

from enum import Enum

from .bs.update import BSPrices
from .collection import load_collections
from .contract import BSContractCalc, STContractCalc, LFContractCalc
from .conversion import FloatRange, get_condition_range
from .price import STPriceManager, load_bck_prices, load_hexa_prices, load_lf_prices, LFPriceManager, load_bs_prices, \
    BSPriceManager, load_bs_sales
from .type.contract import ContractReturn, ItemReturn
from .type.item import to_st_track, ItemRarity
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


collections = load_collections()
roi_list: List[ContractReturn] = []
returns: List[ItemReturn] = []

model = Model.from_str(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] else Model.LF
if not model:
    raise AssertionError(f'Could not determine model from string value \'{sys.argv[1]}\'')
else:
    print(f'Loading model {model.name}')

if model == Model.LF:
    prices: LFPrices = load_lf_prices()
    price_manager = LFPriceManager(prices)
    calc = LFContractCalc(collections, price_manager, required_available=1)

if model == Model.BS:
    prices: BSPrices = load_bs_prices()
    sales = load_bs_sales()
    price_manager = BSPriceManager(prices, sales)
    calc = BSContractCalc(collections, price_manager)
else:
    prices: STPrices = load_hexa_prices() if model == Model.HX else load_bck_prices()
    price_manager = STPriceManager(prices, collections)
    calc = STContractCalc(collections, price_manager,
                          required_sold_amount=10, possible_price_discount=0.1, return_commission=0.09)

for col_name, collection in collections.items():
    for item in collection.items:
        if item.rarity < ItemRarity.COVERT:
            time_range: PriceTimeRange = PriceTimeRange.DAYS_30
            st_item = to_st_track(item)
            for i in [item, st_item]:
                returns += calc.get_item_returns(i, time_range)

collection_name = None
for i in sorted(returns,
                key=operator.attrgetter('item.collection_name', 'item.rarity', 'item_condition',
                                        'item.full_name', 'item_revenue'),
                reverse=True):
    if i.item_roi >= 0 and i.item_revenue > 5 and len(i.conversion_items) <= 30:
        if i.item.collection_name != collection_name:
            collection_name = i.item.collection_name
            print('\n' + collection_name)
        guaranteed = '(100%) ' if i.guaranteed else ''
        item_range = FloatRange(get_condition_range(i.item_condition).min_value, i.float_range.max_value)
        print(f'{guaranteed}[{i.item.rarity}] {i.item_float} {i.float_range} '
              f'{i.item.full_name} ({str(i.item_condition)}) {i.item_investment:.2f}: '
              f'{i.item_revenue:.2f} ({i.item_roi * 100:.0f}%):')
        pretty_print_items(i.conversion_items)
