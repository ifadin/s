from abc import ABC, abstractmethod
from collections import Counter
from itertools import combinations
from operator import attrgetter
from statistics import mean
from typing import List, Optional, Set, Dict, NamedTuple, Tuple

from csgo.collection import get_next_level_items
from csgo.conversion import get_item_to_item_conversions, get_item_possible_conditions, FloatRange, \
    get_item_conversions, get_condition_from_float, get_conversion_required_ranges
from csgo.price import STPriceManager, LFPriceManager, PriceManager, BSPriceManager
from csgo.type.contract import ContractReturn, ItemReturn
from csgo.type.item import Item, ItemCollection, ItemCondition, ItemRarity, ItemWithCondition
from csgo.type.price import PriceTimeRange, get_item_price_name, ItemWithPrice

ContractCandidatesMap = Dict[ItemCondition, Dict[ItemRarity, List[Item]]]


class ItemConversionResult(NamedTuple):
    item: Item
    item_condition: ItemCondition
    item_conversions: Dict[str, Dict[FloatRange, float]]
    range_markers_set: Set[float]
    price_warning: bool = None


class ContractItem(NamedTuple):
    item: Item
    item_price: float
    item_float: float


class ContractCalc(ABC):

    @abstractmethod
    def get_item_returns(self, item: Item, price_time_range: PriceTimeRange) -> List[ItemReturn]:
        pass


class BSContractCalc(ContractCalc):

    def __init__(self, collections: Dict[str, ItemCollection], price_manager: BSPriceManager,
                 sale_commission: float = 0.1) -> None:
        self.collections = collections
        self.price_manager = price_manager
        self.sale_commission = sale_commission

    def get_item_returns(self, item: Item, price_time_range: PriceTimeRange = None) -> List[ItemReturn]:
        item_returns = []
        item_collection = self.collections[item.collection_name]
        for item_condition in get_item_possible_conditions(item):
            conversions = get_item_conversions(item, item_condition, item_collection)
            for item_range, conversion_items in conversions.items():
                guaranteed = len(conversion_items) == 1
                item_return = get_conversion_items_return(conversion_items, self.price_manager)
                if item_return:
                    for item_price in self.price_manager.get_sale_prices(item, item_condition):
                        if item_price.float_value in item_range:
                            conv_items_with_price: Dict[str, float] = {
                                get_item_price_name(c_item, c_item_condition):
                                    self.price_manager.get_avg_price(c_item, c_item_condition)
                                for c_item, c_item_condition in conversion_items.items()
                            }
                            item_investment = item_price.price * 10
                            item_returns.append(
                                ItemReturn(item,
                                           item_condition,
                                           item_investment,
                                           item_return * (1 - self.sale_commission),
                                           item_range,
                                           item_float=item_price.float_value,
                                           guaranteed=guaranteed,
                                           conversion_items=conv_items_with_price))
        return item_returns


class STContractCalc(ContractCalc):

    def __init__(self, collections: Dict[str, ItemCollection],
                 price_manager: STPriceManager,
                 required_sold_amount: int = None,
                 possible_price_discount: float = 0,
                 return_commission: float = 0,
                 with_price_fallback: bool = True) -> None:
        self.collections = collections
        self.price_manager = price_manager
        self.required_sold_amount = required_sold_amount
        self.possible_price_discount = possible_price_discount
        self.return_commission = return_commission
        self.with_price_fallback = with_price_fallback

    def get_item_returns(self, item: Item, price_time_range: PriceTimeRange) -> List[ItemReturn]:
        item_collection = self.collections[item.collection_name]
        item_roi: List[ItemReturn] = []
        for item_condition in get_item_possible_conditions(item):
            items_sold = self.price_manager.get_sold(item, item_condition, price_time_range)
            if (items_sold and items_sold >= self.required_sold_amount) if self.required_sold_amount else True:
                item_roi += get_item_range_rois(item, item_condition, item_collection, self.price_manager,
                                                price_time_range,
                                                self.possible_price_discount, self.return_commission,
                                                self.with_price_fallback)
        return item_roi


class LFContractCalc(ContractCalc):

    def __init__(self, collections: Dict[str, ItemCollection],
                 price_manager: LFPriceManager,
                 required_available: int = 0,
                 return_commission: float = 0.05) -> None:
        self.collections = collections
        self.price_manager = price_manager
        self.required_available = required_available
        self.return_commission = return_commission

    def get_item_returns(self, item: Item, price_time_range: PriceTimeRange) -> List[ItemReturn]:
        item_collection = self.collections[item.collection_name]

        item_roi: List[ItemReturn] = []
        for item_condition in get_item_possible_conditions(item):
            items_available = self.price_manager.get_available(item, item_condition)
            if items_available and items_available >= self.required_available:
                item_roi += get_item_range_rois(item, item_condition, item_collection, self.price_manager,
                                                None, 0, self.return_commission)

        return item_roi


def get_conversion_items_return(conversion_items: Dict[Item, ItemCondition],
                                price_manager: PriceManager) -> Optional[float]:
    total_return = 0
    for item, item_condition in conversion_items.items():
        item_price = price_manager.get_avg_price(item, item_condition)
        if not item_price:
            # print(f'[WARN] price for {item.full_name} ({str(item_condition)}) not found')
            return None
        total_return += item_price
    return total_return / len(conversion_items)


def get_item_range_rois(item: Item,
                        item_condition: ItemCondition,
                        item_collection: ItemCollection,
                        price_manager: PriceManager,
                        price_time_range: PriceTimeRange,
                        possible_price_discount: float,
                        return_commission: float,
                        with_price_fallback: bool = True) -> List[ItemReturn]:
    next_items = get_next_level_items(item, item_collection)
    if not next_items:
        return []

    item_price = price_manager.get_avg_price(item, item_condition, price_time_range, with_price_fallback)
    if not item_price:
        return []

    conversion_result = get_item_conversion_result(item, item_condition, item_collection,
                                                   price_manager, price_time_range, with_price_fallback)
    item_roi: List[ItemReturn] = []
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
            item_return = sum(range_return) * (1 - return_commission) / len(range_return)
            item_investment = item_price * 10 * (1 - possible_price_discount)
            guaranteed = len(next_items) == 1
            item_roi.append(ItemReturn(
                item, item_condition, item_investment, item_return, item_float_range,
                guaranteed=guaranteed, conversion_items=range_items))

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
        for n_item_cond, float_range in get_item_to_item_conversions(item, item_condition, n_item).items():
            n_item_price = price_manager.get_avg_price(n_item, n_item_cond,
                                                       price_time_range, with_price_fallback)
            return_key = f'{n_item.full_name} ({str(n_item_cond)})'
            if n_item_price:
                if n_item not in item_conversions:
                    item_conversions[return_key] = {}
                range_markers_set.add(float_range.min_value)
                range_markers_set.add(float_range.max_value)

                item_conversions[return_key][float_range] = n_item_price
            else:
                print(f'[WARN] price for item {n_item.full_name} ({str(n_item_cond)}) not found')
                price_warning = True

    return ItemConversionResult(item, item_condition, item_conversions, range_markers_set, price_warning)


def get_trade_contract_return(items: List[ContractItem],
                              price_manager: PriceManager,
                              collections: Dict[str, ItemCollection],
                              commission: float = 0.1) -> ContractReturn:
    warnings = validate_contract_items(items, collections)

    avg_float: float = mean([i.item_float for i in items])
    investment: float = sum([i.item_price for i in items])

    conversion_items = get_contract_conversion_items([i.item for i in items], avg_float, collections)
    outcome_items: List[ItemWithPrice] = []
    result: float = 0
    for o_item, o_item_condition in conversion_items:
        o_item_price = price_manager.get_avg_price(o_item, o_item_condition)
        if not o_item_price:
            raise AssertionError(f'Item {o_item.full_name} has no price')
        result += o_item_price
        outcome_items.append(ItemWithPrice(o_item, o_item_price, o_item_condition))

    c_return = result / len(conversion_items) * (1 - commission)
    return ContractReturn(outcome_items, investment, c_return, avg_float, warnings=warnings)


def validate_contract_items(items: List[ContractItem],
                            collections: Dict[str, ItemCollection]) -> List[str]:
    if len(items) != 10:
        raise AssertionError('Contract must be of length 10')

    warnings = []
    avg_float: float = mean([i.item_float for i in items])
    rarity = items[0].item.rarity
    st_track = items[0].item.st_track
    for c_item in items:
        if c_item.item.st_track != st_track:
            raise AssertionError(f'Item {c_item.item.full_name} has different st_track value')
        if c_item.item.rarity != rarity:
            raise AssertionError(f'Item {c_item.item.full_name} has different rarity')

        potential_float_range = get_item_conversion_float_range(c_item.item, c_item.item_float,
                                                                collections[c_item.item.collection_name])
        if not potential_float_range:
            raise AssertionError(f'Item {c_item.item.full_name} cannot be converted')
        if avg_float not in potential_float_range:
            warnings.append(f'{c_item.item.full_name}: avg float {avg_float} '
                            f'is out of effective range {potential_float_range}')
    return warnings


def get_item_conversion_float_range(item: Item,
                                    item_float: float,
                                    item_collection: ItemCollection) -> FloatRange:
    item_condition = get_condition_from_float(item_float)
    conversions = get_item_conversions(item, item_condition, item_collection)
    return next((f_range for f_range in conversions if item_float in f_range), None)


def get_contract_conversion_items(items: List[Item],
                                  avg_float: float,
                                  collections: Dict[str, ItemCollection]) -> List[ItemWithCondition]:
    outcomes: List[ItemWithCondition] = []
    for item in items:
        next_items = get_next_level_items(item, collections[item.collection_name])
        if not next_items:
            raise AssertionError(f'Item {item.full_name} has no conversion outcomes')
        for target_item in next_items:
            target_item_condition = next((
                conv_cond
                for conv_cond, conversion_range in get_conversion_required_ranges(target_item).items()
                if avg_float in conversion_range
            ), None)
            if not target_item_condition:
                raise AssertionError(f'Item {target_item.full_name} cannot be converted from float {avg_float}')
            outcomes.append((target_item, target_item_condition))
    return outcomes


def get_approximated_prices(item: Item, item_condition: ItemCondition,
                            price_manager: STPriceManager,
                            price_time_range: PriceTimeRange,
                            price_approximation_by_collection: bool,
                            price_approximation_by_condition: bool) -> List[float]:
    approx_by_collection = (price_manager.get_approx_price(item, item_condition, price_time_range)
                            if price_approximation_by_collection else None)
    approx_by_condition = (price_manager.get_approx_price_from_rarity(item, item_condition, price_time_range)
                           if price_approximation_by_condition else None)

    return (([approx_by_collection] if approx_by_collection else []) +
            ([approx_by_condition] if approx_by_condition else []))


def get_best_contracts(items: Set[ContractItem], price_manager: PriceManager,
                       collections: Dict[str, ItemCollection], commission: float):
    item_sets = get_contract_items_sets(items)
    for item_rarity, (basic_items, st_ct_items) in item_sets.items():
        st = False
        for c_items in [basic_items, st_ct_items]:
            print(f"[{item_rarity}] {len(c_items)} {'st' if st else 'basic'}")
            if len(c_items) >= 10:
                contract = sorted([
                    get_trade_contract_return(list(c), price_manager, collections, commission)
                    for c in combinations(c_items, 10)
                ], key=attrgetter('contract_revenue'), reverse=True)[0]
                print_contract_return(contract)
                print()
            st = True


def get_contract_items_sets(items: Set[ContractItem]) -> Dict[ItemRarity, Tuple[Set[ContractItem], Set[ContractItem]]]:
    items_set = {}
    for c_item in items:
        item = c_item.item
        r = ItemRarity(item.rarity)
        if r not in items_set:
            items_set[r] = (set(), set())

        set_items, ct_set_items = items_set[r]
        if item.st_track:
            ct_set_items.add(c_item)
        else:
            set_items.add(c_item)

    return items_set


def print_contract_return(c: ContractReturn):
    counter = Counter(c.outcome_items)
    print(f'I:{c.contract_investment:.2f} R:{c.contract_revenue:.2f} ROI:{c.contract_roi * 100:.0f}% F:{c.avg_float}')
    warnings = c.warnings
    for w in warnings:
        print(f'[WARN] {w}')
    for c_res, freq in counter.items():
        prob = freq / len(c.outcome_items) * 100
        print(f' - {prob:.2f}% {c_res.item.full_name} ({str(c_res.item_condition)}) {c_res.item_price:.2f}')
