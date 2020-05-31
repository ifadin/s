import operator
from collections import Counter
from typing import List

from .contract import calculate_trade_contract_return, get_contract_candidates
from .load import load_collections, load_bck_prices, load_hexa_prices
from .price import PriceManager
from .type.contract import ContractReturn
from .type.item import Item
from .type.price import PriceTimeRange, STPrices


def items_list_to_str(items: List[Item]) -> str:
    c = Counter(items)
    res_str = ''
    for item, item_freq in c.items():
        res_str += f'{item_freq} {item.name} ({item.rarity}) ({item.collection_name}), '

    return res_str


collections = load_collections()
prices: STPrices = load_hexa_prices() if True else load_bck_prices()
price_manager = PriceManager(prices, collections)
roi_list: List[ContractReturn] = []
time_range: PriceTimeRange = PriceTimeRange.DAYS_30

contract_candidates = get_contract_candidates(price_manager, time_range,
                                              required_sold_amount=30, possible_outcomes_limit=10)

for item_condition, rarity_details in contract_candidates.items():
    for rarity, items in rarity_details.items():
        for item in items:
            collection = collections[item.collection_name]
            for other_item in items:
                other_collection = collections[other_item.collection_name]
                contract_items = [(item, collection)] + [(other_item, other_collection) for i in range(0, 9)]
                contract_return = calculate_trade_contract_return(
                    contract_items, item_condition, price_manager, time_range,
                    price_approximation_by_condition=True, price_approximation_by_collection=False)
                if contract_return:
                    roi_list.append(contract_return)

for ct in sorted(roi_list, key=operator.attrgetter('contract_revenue'), reverse=True):
    if ct.contract_roi >= 0.15 and ct.contract_revenue > 5 and ct.contract_investment < 20:
        approx = '(approx) ' if ct.approximated else ''
        guaranteed = '(100%) ' if ct.guaranteed else ''
        ct_items_str = f'[{items_list_to_str(ct.items)}]'
        print(f'{approx}{guaranteed}{str(ct.item_condition)} {ct_items_str} {ct.contract_investment:.2f}: '
              f'{ct.contract_revenue:.2f} ({ct.contract_roi * 100:.0f}%)')
