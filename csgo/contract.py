from abc import ABC, abstractmethod
from collections import Counter
from itertools import combinations
from operator import attrgetter, itemgetter
from statistics import mean
from typing import List, Optional, Set, Dict, NamedTuple, Iterable, Tuple

from csgo.collection import get_next_level_items, get_item_from_collection
from csgo.conversion import get_item_to_item_conversions, get_item_possible_conditions, get_item_conversions, \
    get_condition_from_float, get_condition_range, get_conversion_required_ranges, ConversionMap
from csgo.price import STPriceManager, PriceManager, LFPriceManager, DMPriceManager
from csgo.type.contract import ContractReturn, ItemReturn, OutputItems, ContractItem
from csgo.type.float import FloatRange
from csgo.type.item import Item, ItemCollection, ItemCondition, ItemRarity, ItemWithCondition, to_st_track
from csgo.type.price import PriceTimeRange, get_market_name, ItemWithPrice, PriceEntry

ContractCandidatesMap = Dict[ItemCondition, Dict[ItemRarity, List[Item]]]


class ItemConversionResult(NamedTuple):
    item: Item
    item_condition: ItemCondition
    item_conversions: Dict[str, Dict[FloatRange, float]]
    range_markers_set: Set[float]
    price_warning: bool = None


class ItemReturnCalc(ABC):

    @abstractmethod
    def get_item_returns(self, item: Item, price_time_range: PriceTimeRange) -> List[ItemReturn]:
        pass


class BSItemReturnCalc(ItemReturnCalc):

    def __init__(self, conversion_map: ConversionMap, price_manager: PriceManager,
                 sale_commission: float = 0.1) -> None:
        self.conversion_map = conversion_map
        self.price_manager = price_manager
        self.sale_commission = sale_commission

    def get_item_returns(self, item: Item, price_time_range: PriceTimeRange = None) -> List[ItemReturn]:
        returns: List[ItemReturn] = []
        conversion_rules = self.conversion_map.get_rules(item)
        for conversion_range, conversion_items in conversion_rules.items():
            item_condition = conversion_range.item_condition
            contract_return = get_conversion_items_return(conversion_items, self.price_manager)

            if contract_return:
                for item_on_sale in self.price_manager.get_items_on_sale(item, item_condition):
                    if item_on_sale.float_value in conversion_range:
                        output_items = to_output_items(conversion_items, self.price_manager)
                        item_investment = item_on_sale.price * 10
                        item_return = contract_return * (1 - self.sale_commission)

                        returns.append(ItemReturn(
                            item, item_condition,
                            item_investment, item_return, conversion_range,
                            item_float=item_on_sale.float_value, output_items=output_items, item_id=item_on_sale.item_id
                        ))

        return returns


class STItemReturnCalc(ItemReturnCalc):

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


class LFItemReturnCalc(BSItemReturnCalc):

    def __init__(self, conversion_map: ConversionMap, price_manager: LFPriceManager,
                 sale_commission: float = 0.05) -> None:
        super().__init__(conversion_map, price_manager, sale_commission)
        self.price_manager = price_manager

    def get_potential_item_returns(self, item: Item, required_available: int = 0) -> List[ItemReturn]:
        returns: List[ItemReturn] = []
        conversion_rules = self.conversion_map.get_rules(item)
        for conversion_range, conversion_items in conversion_rules.items():
            item_condition = conversion_range.item_condition
            items_available = self.price_manager.get_available(item, item_condition)

            if items_available and items_available >= required_available:
                item_price = self.price_manager.get_avg_price(item, item_condition)
                if item_price:
                    investment = item_price * 10
                    item_return = get_conversion_items_return(conversion_items, self.price_manager)

                    if item_return:
                        output_items = to_output_items(conversion_items, self.price_manager)
                        returns.append(ItemReturn(
                            item, item_condition,
                            investment, item_return * (1 - self.sale_commission), conversion_range,
                            output_items=output_items
                        ))
        return returns


class DMItemReturnCalc(BSItemReturnCalc):

    def __init__(self, conversion_map: ConversionMap, price_manager: DMPriceManager,
                 sale_commission: float = 0) -> None:
        super().__init__(conversion_map, price_manager, sale_commission)
        self.price_manager = price_manager


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


def to_output_items(conversion_items: Dict[Item, ItemCondition], price_manager: PriceManager) -> OutputItems:
    return {get_market_name(item, item_condition): price_manager.get_avg_price(item, item_condition)
            for item, item_condition in conversion_items.items()}


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
            item_roi.append(ItemReturn(
                item, item_condition, item_investment, item_return, item_float_range, output_items=range_items))

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
                              buy_reduction: float = 1,
                              sale_commission: float = 0.1,
                              strict: bool = True) -> Tuple[Optional[ContractReturn], Set[str]]:
    warnings = validate_contract_items(items, collections, strict)

    avg_float: float = mean([i.price_entry.float_value for i in items])
    investment: float = sum([i.price_entry.price for i in items]) * buy_reduction

    conversion_items = get_contract_conversion_items([i.item for i in items], avg_float, collections)
    outcome_items: List[ItemWithPrice] = []
    result: float = 0
    for o_item, o_item_condition in conversion_items:
        o_item_price = price_manager.get_avg_price(o_item, o_item_condition)
        if not o_item_price:
            warnings.add(f'Price for {o_item.full_name} not found, calculation skipped')
            return None, warnings
        result += o_item_price
        outcome_items.append(ItemWithPrice(o_item, o_item_price, o_item_condition))

    c_return = result / len(conversion_items) * (1 - sale_commission)
    return ContractReturn(items, outcome_items, investment, c_return, avg_float, warnings=warnings), warnings


def validate_contract_items(items: List[ContractItem],
                            collections: Dict[str, ItemCollection],
                            strict: bool = True) -> Set[str]:
    if strict and len(items) != 10:
        raise AssertionError('Contract must be of length 10')

    warnings = set()
    avg_float: float = mean([i.price_entry.float_value for i in items])
    rarity = items[0].item.rarity
    st_track = items[0].item.st_track
    for c_item in items:
        if c_item.item.st_track != st_track:
            raise AssertionError(f'Item {c_item.item.full_name} has different st_track value')
        if c_item.item.rarity != rarity:
            raise AssertionError(f'Item {c_item.item.full_name} has different rarity')

        potential_float_range = get_item_conversion_float_range(c_item.item, c_item.price_entry.float_value,
                                                                collections[c_item.item.collection_name])
        if not potential_float_range:
            raise AssertionError(f'Item {c_item.item.full_name} cannot be converted')
        if avg_float >= potential_float_range.max_value:
            warnings.add(f'{c_item.item.full_name}: avg float {avg_float} '
                         f'is out of the effective range {potential_float_range}')
    return warnings


def get_item_conversion_float_range(item: Item,
                                    item_float: float,
                                    item_collection: ItemCollection) -> Optional[FloatRange]:
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
                       collections: Dict[str, ItemCollection],
                       buy_reduction: float,
                       sale_commission: float,
                       strict: bool = True,
                       withdrawable_in: int = None):
    item_sets = get_contract_items_sets(items)
    print_items_set_details(item_sets, collections, withdrawable_in)
    print()
    for item_rarity, condition_set in sorted(item_sets.items(), key=itemgetter(0)):
        for item_condition, (basic_items, st_items) in sorted(condition_set.items(), key=itemgetter(0)):
            next_cond_b_items, next_cond_st_items = (
                condition_set.get(ItemCondition(item_condition - 1), (set(), set()))
                if item_condition != ItemCondition.BATTLE_SCARED else (set(), set()))

            st = False
            for c_items in [basic_items, st_items]:
                if c_items:
                    item_combinations = combinations(c_items, 10 if len(c_items) >= 10 else len(c_items))
                    contracts_results = []
                    for comb in item_combinations:
                        next_items = next_cond_st_items if st else next_cond_b_items
                        candidates = set(filter_withdrawable(
                            get_contract_candidates(comb, next_items, collections), withdrawable_in))
                        if candidates and (len(candidates) == 10 if strict else True):
                            c, warnings = get_trade_contract_return(
                                comb, price_manager, collections,
                                buy_reduction=buy_reduction, sale_commission=sale_commission, strict=strict
                            )
                            if c:
                                contracts_results.append(c)
                    if contracts_results:
                        print(f'[{item_rarity}]{" ST" if st else ""} {str(item_condition)}:')
                        contract = sorted(contracts_results,
                                          key=attrgetter('contract_revenue', 'avg_float'), reverse=True)[0]
                        print_contract_return(contract)
                        print()
                st = True


def get_underperforming_items(items: Iterable[ContractItem],
                              collections: Dict[str, ItemCollection]) -> Dict[ContractItem, FloatRange]:
    if not items:
        return {}
    avg_float: float = mean([i.price_entry.float_value for i in items])
    underperforming = {}
    for i in items:
        potential_float_range = get_item_conversion_float_range(i.item, i.price_entry.float_value,
                                                                collections[i.item.collection_name])
        if potential_float_range and avg_float >= potential_float_range.max_value:
            underperforming[i] = potential_float_range
    return underperforming


def get_contract_candidates(items: Set[ContractItem],
                            next_level_items: Set[ContractItem],
                            collections: Dict[str, ItemCollection]) -> Iterable[ContractItem]:
    u = get_underperforming_items(items, collections)
    candidates = set(items).difference(u.keys()) if len(u) <= int(len(items) / 2) else set(u.keys())
    if not candidates:
        return []
    if len(candidates) >= 10:
        return candidates
    extra = sorted(next_level_items, key=attrgetter('price_entry.float_value'))[0:10 - len(items) + len(u)]
    return candidates | set(extra)


ContractItemsSet = Dict[ItemRarity, Dict[ItemCondition, Tuple[Set[ContractItem], Set[ContractItem]]]]


def get_contract_items_sets(items: Set[ContractItem]) -> ContractItemsSet:
    items_set = {}
    for c_item in items:
        item = c_item.item
        r = ItemRarity(item.rarity)

        if r not in items_set:
            items_set[r] = {}

        for item_condition in ItemCondition:
            if c_item.price_entry.float_value in get_condition_range(item_condition):
                if item_condition not in items_set[r]:
                    items_set[r][item_condition] = (set(), set())

                if item.st_track:
                    items_set[r][item_condition][1].add(c_item)
                else:
                    items_set[r][item_condition][0].add(c_item)

    return items_set


def to_contract_item(p: PriceEntry, collections: Dict[str, ItemCollection]) -> ContractItem:
    item = get_item_from_collection(p.item_name, collections)
    if p.st_track:
        item = to_st_track(item)
    return ContractItem(item, p)


def print_contract_return(c: ContractReturn):
    counter = Counter(c.outcome_items)
    print(f'I:{c.contract_investment:.2f} ROI:{c.contract_roi * 100:.0f}% F:{c.avg_float}')
    for in_item in c.source_items:
        in_market = ' M ' if in_item.price_entry.in_market else ''
        withdrawable_in = f'({in_item.price_entry.withdrawable_in / 24:.1f}d) ' if in_item.price_entry.withdrawable_in else ''
        print(f' - {in_market}{withdrawable_in}{in_item.price_entry.market_hash_name} '
              f'{in_item.price_entry.price:.2f} {in_item.price_entry.float_value}')
    print('\t\t\t||')
    print('\t\t\t\\/')
    warnings = c.warnings
    for w in warnings:
        print(f'[WARN] {w}')
    print(f'R:{c.contract_return:.2f}')
    for o_item, freq in sorted(counter.items(), key=itemgetter(1), reverse=True):
        prob = freq / len(c.outcome_items) * 100
        print(f' - {prob:.2f}% {o_item.market_name} {o_item.item_price:.2f}')


def print_items_set_details(items_set: ContractItemsSet, collections: Dict[str, ItemCollection],
                            withdrawable_in: int = None):
    for item_rarity, items_by_condition in sorted(items_set.items(), key=itemgetter(0)):
        for item_condition, (basic_items, st_items) in sorted(items_by_condition.items(), key=itemgetter(0)):
            st = False
            for items in [set(filter_withdrawable(basic_items, withdrawable_in)),
                          set(filter_withdrawable(st_items, withdrawable_in))]:
                avg_float = mean([i.price_entry.float_value for i in items]) if items else 0
                print(f"[{item_rarity}] {str(item_condition)}: {len(items)} {'st' if st else 'basic'} ({avg_float})")
                for r in get_underperforming_items(items, collections).values():
                    print(f'\t- avg float is out of the range {r}')
                st = True


def filter_withdrawable(items: Iterable[ContractItem], withdrawable_in: int = None) -> Iterable[ContractItem]:
    if not withdrawable_in:
        return items
    return (i for i in items if not i.price_entry.withdrawable_in or i.price_entry.withdrawable_in < withdrawable_in)
