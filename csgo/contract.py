from statistics import mean
from typing import List, Tuple, Optional, Set, Dict, NamedTuple

from csgo.collection import get_next_level_items
from csgo.condition import get_item_possible_conversions, get_item_possible_conditions, FloatRange
from csgo.price import PriceManager
from csgo.type.contract import ContractReturn, ItemReturn
from csgo.type.item import Item, ItemCollection, ItemCondition, ItemRarity
from csgo.type.price import PriceTimeRange

ContractCandidatesMap = Dict[ItemCondition, Dict[ItemRarity, List[Item]]]


class ItemConversionResult(NamedTuple):
    item: Item
    item_condition: ItemCondition
    item_conversions: Dict[str, Dict[FloatRange, float]]
    range_markers_set: Set[float]
    price_warning: bool = None


def get_item_conversion_return(item: Item,
                               item_collection: ItemCollection,
                               price_manager: PriceManager,
                               price_time_range: PriceTimeRange,
                               required_sold_amount: int = None,
                               possible_price_discount: float = 0,
                               return_commission: float = 0,
                               with_price_fallback: bool = True) -> List[ItemReturn]:
    next_items = get_next_level_items(item, item_collection)
    if not next_items:
        return []

    item_roi = []
    for item_condition in get_item_possible_conditions(item):
        item_price = price_manager.get_avg_price(item, item_condition, price_time_range, with_price_fallback)
        items_sold = price_manager.get_sold(item, item_condition, price_time_range)
        if item_price and (items_sold and items_sold >= required_sold_amount if required_sold_amount else True):
            conversion_result = get_item_conversion_result(item, item_condition, item_collection,
                                                           price_manager, price_time_range, with_price_fallback)

            range_markers = sorted(list(conversion_result.range_markers_set))
            for marker_index in range(0, len(range_markers) - 1):
                left_marker = range_markers[marker_index]
                right_marker = range_markers[marker_index + 1]
                item_float_range = FloatRange(left_marker, right_marker)

                range_items: Dict[str, float] = {}
                range_return: List[float] = []
                for conv_item_name, conversion_ranges in conversion_result.item_conversions.items():
                    converted_price = next(
                        (item_price for return_range, item_price in conversion_ranges.items()
                         if left_marker >= return_range.min_value and right_marker <= return_range.max_value),
                        None)
                    if converted_price:
                        range_return.append(converted_price)
                        range_items[conv_item_name] = converted_price

                if range_return and not conversion_result.price_warning:
                    item_return = sum(range_return) * (1 - return_commission) / len(range_return) / 10
                    item_std = price_manager.get_std(item, item_condition, price_time_range)
                    std_amplitude = item_std / item_price if item_std else 1
                    item_buy_price = (item_price - item_std
                                      if item_std and std_amplitude < possible_price_discount
                                      else item_price * (1 - possible_price_discount))
                    guaranteed = len(next_items) == 1
                    item_roi.append(ItemReturn(
                        item, item_condition, item_buy_price, item_return, item_float_range, guaranteed, range_items))

    return item_roi


def get_item_conversion_result(item: Item,
                               item_condition: ItemCondition,
                               item_collection: ItemCollection,
                               price_manager: PriceManager,
                               price_time_range: PriceTimeRange,
                               with_price_fallback: bool = True) -> ItemConversionResult:
    price_warning: bool = False
    range_markers_set: Set[float] = set()
    item_conversions = {}
    for n_item in get_next_level_items(item, item_collection):
        for n_item_cond, float_range in get_item_possible_conversions(item, item_condition, n_item).items():
            n_item_price = price_manager.get_avg_price(n_item, n_item_cond,
                                                       price_time_range, with_price_fallback)
            return_key = f'{n_item.name} ({str(n_item_cond)})'
            if n_item_price:
                if n_item not in item_conversions:
                    item_conversions[return_key] = {}
                range_markers_set.add(float_range.min_value)
                range_markers_set.add(float_range.max_value)

                item_conversions[return_key][float_range] = n_item_price
            else:
                print(f'[WARN] price for item {n_item.name} ({str(n_item_cond)}) not found')
                price_warning = True

    return ItemConversionResult(item, item_condition, item_conversions, range_markers_set, price_warning)


def get_contract_candidates(price_manager: PriceManager, time_range: PriceTimeRange,
                            required_sold_amount: int = None,
                            possible_outcomes_limit: int = None) -> ContractCandidatesMap:
    res: ContractCandidatesMap = {}
    for item_cond in ItemCondition:
        for col_name, col in price_manager.collections.items():
            lowest_items = price_manager.find_lowest_price_items(col_name, item_cond, time_range)
            for item_rarity, item in lowest_items.items():
                items_sold = price_manager.get_sold(item, item_cond, time_range)
                nxt_items = get_next_level_items(item, col)
                if (nxt_items
                        and (items_sold > required_sold_amount if required_sold_amount else True)
                        and (len(nxt_items) <= possible_outcomes_limit if possible_outcomes_limit else True)):
                    if item_cond not in res:
                        res[item_cond] = {}
                    res[item_cond][item_rarity] = [item] + (res[item_cond][item_rarity]
                                                            if item_rarity in res[item_cond] else [])
    return res


def calculate_trade_contract_return(contract_items: List[Tuple[Item, ItemCollection]],
                                    item_condition: ItemCondition,
                                    price_manager: PriceManager,
                                    price_time_range: PriceTimeRange = PriceTimeRange.DAYS_30,
                                    price_approximation_by_collection: bool = False,
                                    price_approximation_by_condition: bool = False,
                                    buy_price_reduction: float = 0.9) -> Optional[ContractReturn]:
    if len(contract_items) != 10:
        raise AssertionError('Contract items length must be 10')

    approximated: bool = False

    contract_items_values: List[float] = []
    contract_items_expected_return: List[float] = []
    contract_possible_items: Set[Item] = set()
    for item, item_collection in contract_items:
        item_price = price_manager.get_avg_price(item, item_condition, price_time_range)
        if not item_price:
            return None
        contract_items_values.append(item_price * buy_price_reduction)

        next_items = get_next_level_items(item, item_collection)
        next_items_prices: List[float] = []
        for n_item in next_items:
            contract_possible_items.add(n_item)
            n_item_price = price_manager.get_avg_price(n_item, item_condition, price_time_range)
            if not n_item_price:
                if price_approximation_by_collection or price_approximation_by_condition:
                    approx_prices = get_approximated_prices(n_item, item_condition,
                                                            price_manager, price_time_range,
                                                            price_approximation_by_collection,
                                                            price_approximation_by_condition)
                    approximated = True
                    n_item_price = mean(approx_prices) if approx_prices else None

            if not n_item_price:
                return None
            else:
                next_items_prices.append(n_item_price)
        next_item_expected_value = sum(next_items_prices) / len(next_items_prices)
        contract_items_expected_return.append(next_item_expected_value)

    items = [item for item, _ in contract_items]
    guaranteed = len(contract_possible_items) == 1
    contract_investment = sum(contract_items_values)
    contract_expected_revenue = sum(contract_items_expected_return) / 10
    return ContractReturn(items, item_condition, contract_investment, contract_expected_revenue, approximated,
                          guaranteed)


def get_approximated_prices(item: Item, item_condition: ItemCondition,
                            price_manager: PriceManager,
                            price_time_range: PriceTimeRange,
                            price_approximation_by_collection: bool,
                            price_approximation_by_condition: bool) -> List[float]:
    approx_by_collection = (price_manager.get_approx_price(item, item_condition, price_time_range)
                            if price_approximation_by_collection else None)
    approx_by_condition = (price_manager.get_approx_price_from_rarity(item, item_condition, price_time_range)
                           if price_approximation_by_condition else None)

    return (([approx_by_collection] if approx_by_collection else []) +
            ([approx_by_condition] if approx_by_condition else []))
