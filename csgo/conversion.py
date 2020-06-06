from typing import NamedTuple, Dict, List, Set, Tuple

from csgo.collection import get_next_level_items
from csgo.type.item import ItemCondition, Item, ItemCollection

eps = 0.000000000001


class FloatRange(NamedTuple):
    min_value: float
    max_value: float

    def __contains__(self, value: float) -> bool:
        return self.min_value < value < self.max_value

    def __str__(self) -> str:
        return f'[{self.min_value}, {self.max_value}]'


ItemWithCondition = Tuple[Item, ItemCondition]
ItemConversions = Dict[FloatRange, Dict[Item, ItemCondition]]


def is_in_float_range(src_float_range: FloatRange, target_float_range: FloatRange) -> bool:
    return target_float_range.min_value <= src_float_range.min_value and src_float_range.max_value <= target_float_range.max_value


def get_condition_range(cond: ItemCondition) -> FloatRange:
    ranges = {
        ItemCondition.BATTLE_SCARED: FloatRange(0.45, 1),
        ItemCondition.WELL_WORN: FloatRange(0.38, 0.45),
        ItemCondition.FIELD_TESTED: FloatRange(0.15, 0.38),
        ItemCondition.MINIMAL_WEAR: FloatRange(0.07, 0.15),
        ItemCondition.FACTORY_NEW: FloatRange(0, 0.07)
    }
    return ranges[cond]


def get_conversion_float_value(target_float: float, item: Item) -> float:
    value = (target_float - item.min_float) / (item.max_float - item.min_float)
    return 0 if value < 0 else (1 if value > 1 else value)


def get_conversion_required_ranges(item: Item) -> Dict[ItemCondition, FloatRange]:
    res = {}
    min_conversion_float = 1
    for cond in get_item_possible_conditions(item):
        conversion_float = get_conversion_float_value(get_condition_range(cond).min_value, item)
        res[cond] = FloatRange(conversion_float, min_conversion_float)
        min_conversion_float = conversion_float

    return res


def get_condition_from_float(float_value: float) -> ItemCondition:
    for cond in ItemCondition:
        cond_range = get_condition_range(cond)
        if cond_range.min_value <= float_value:
            if (float_value <= cond_range.max_value
            if cond == ItemCondition.BATTLE_SCARED
            else float_value < cond_range.max_value):
                return cond


def get_item_possible_conditions(item: Item) -> List[ItemCondition]:
    min_cond = get_condition_from_float(item.max_float - eps)
    max_cond = get_condition_from_float(item.min_float)
    return [cond for cond in ItemCondition if min_cond <= cond <= max_cond]


def get_item_condition_ranges(item: Item) -> Dict[ItemCondition, FloatRange]:
    return {
        c: FloatRange(
            item.min_float if item.min_float > get_condition_range(c).min_value else get_condition_range(c).min_value,
            item.max_float if item.max_float < get_condition_range(c).max_value else get_condition_range(c).max_value,
        ) for c in get_item_possible_conditions(item)
    }


def get_item_to_item_conversions(item: Item,
                                 item_condition: ItemCondition,
                                 target_item: Item) -> Dict[ItemCondition, FloatRange]:
    res = {}
    item_condition_range = get_item_condition_ranges(item)[item_condition]
    item_range_left = item_condition_range.min_value
    item_range_right = item_condition_range.max_value
    item_float_range = FloatRange(item_range_left, item_range_right)

    for conv_cond, conversion_range in get_conversion_required_ranges(target_item).items():
        if (item_range_right - eps in conversion_range or
                item_range_left + eps in conversion_range or
                conversion_range.min_value in item_float_range or
                conversion_range.max_value in item_float_range):
            res[conv_cond] = FloatRange(max((item_range_left, conversion_range.min_value)),
                                        min((item_range_right, conversion_range.max_value)))

    return res


def get_item_conversions(item: Item, item_condition: ItemCondition, item_collection: ItemCollection) -> ItemConversions:
    next_items = get_next_level_items(item, item_collection)
    if not next_items:
        return {}

    range_markers_set: Set[float] = set()
    next_level_conversions: Dict[ItemWithCondition, FloatRange] = {}
    for n_item in next_items:
        for n_item_cond, float_range in get_item_to_item_conversions(item, item_condition, n_item).items():
            next_level_conversions[(n_item, n_item_cond)] = float_range
            range_markers_set.add(float_range.min_value)
            range_markers_set.add(float_range.max_value)

    item_conversion: ItemConversions = {}
    range_markers = sorted(list(range_markers_set))
    for marker_index in range(0, len(range_markers) - 1):
        item_float_range = FloatRange(range_markers[marker_index], range_markers[marker_index + 1])
        for (i, i_cond), next_level_range in next_level_conversions.items():
            if is_in_float_range(item_float_range, next_level_range):
                if item_float_range not in item_conversion:
                    item_conversion[item_float_range] = {}
                item_conversion[item_float_range][i] = i_cond

    return item_conversion
