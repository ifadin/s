import operator
from typing import List, Dict

from .collection import load_collections
from .condition import FloatRange, get_condition_range
from .contract import get_item_conversion_return
from .price import PriceManager, load_bck_prices, load_hexa_prices
from .type.contract import ContractReturn, ItemReturn
from .type.item import ItemRarity
from .type.price import PriceTimeRange, STPrices


def pretty_print_items(items: Dict[str, float]):
    for item_name, item_price in items.items():
        print(f'\t - {item_name}: {item_price}')


collections = load_collections()
prices: STPrices = load_hexa_prices() if False else load_bck_prices()
price_manager = PriceManager(prices, collections)
roi_list: List[ContractReturn] = []
time_range: PriceTimeRange = PriceTimeRange.DAYS_30
returns: List[ItemReturn] = []

for col_name, collection in collections.items():
    for item in collection.items:
        if item.rarity < ItemRarity.COVERT:
            returns += get_item_conversion_return(
                item, collection, price_manager, time_range,
                required_sold_amount=10, possible_price_discount=0.1, return_commission=0.15)

for i in sorted(returns, key=operator.attrgetter('item_revenue'), reverse=True):
    if i.item_roi >= 0 and i.item_buy_price < 2000000 and len(i.conversion_items) <= 2:
        guaranteed = '(100%) ' if i.guaranteed else ''
        item_range = FloatRange(get_condition_range(i.item_condition).min_value, i.float_range.max_value)
        print(f'{guaranteed}[{i.item.rarity}] {i.float_range} '
              f'{i.item.name} ({str(i.item_condition)}) {i.item_buy_price * 10:.2f}: '
              f'{i.item_revenue * 10:.2f} ({i.item_roi * 100:.0f}%):')
        pretty_print_items(i.conversion_items)
