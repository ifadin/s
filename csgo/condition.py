from typing import NamedTuple, Dict, List

from csgo.type.item import ItemCondition, Item


class ConditionRange(NamedTuple):
    min_value: float
    max_value: float


def get_condition_range(cond: ItemCondition) -> ConditionRange:
    ranges = {
        ItemCondition.BATTLE_SCARED: ConditionRange(0.45, 1),
        ItemCondition.WELL_WORN: ConditionRange(0.38, 0.45),
        ItemCondition.FIELD_TESTED: ConditionRange(0.15, 0.38),
        ItemCondition.MINIMAL_WEAR: ConditionRange(0.07, 0.15),
        ItemCondition.FACTORY_NEW: ConditionRange(0, 0.07)
    }
    return ranges[cond]


def get_conversion_float_value(target_float: float, item: Item) -> float:
    value = (target_float - item.min_float) / (item.max_float - item.min_float)
    return 0 if value < 0 else (1 if value > 1 else value)


def get_item_conversion_ranges(item: Item) -> Dict[ItemCondition, ConditionRange]:
    res = {}
    min_conversion_float = None
    for c in get_item_possible_conditions(item):
        min_conversion_float = get_condition_range(c).max_value if not min_conversion_float else min_conversion_float
        conversion_float = get_conversion_float_value(get_condition_range(c).min_value, item)
        res[c] = ConditionRange(conversion_float, min_conversion_float)
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
    min_cond = get_condition_from_float(item.max_float)
    max_cond = get_condition_from_float(item.min_float)
    return [cond for cond in ItemCondition if min_cond <= cond <= max_cond]


def get_item_condition_ranges(item: Item) -> Dict[ItemCondition, ConditionRange]:
    return {
        c: ConditionRange(
            item.min_float if item.min_float > get_condition_range(c).min_value else get_condition_range(c).min_value,
            item.max_float if item.max_float < get_condition_range(c).max_value else get_condition_range(c).max_value,
        ) for c in get_item_possible_conditions(item)
    }


def get_item_possible_conversions(item: Item,
                                  item_condition: ItemCondition,
                                  target_item: Item) -> Dict[ItemCondition, float]:
    res = {}
    for item_cond, conversion_range in get_item_conversion_ranges(target_item).items():
        item_left_range = get_item_condition_ranges(item)[item_condition].min_value
        item_right_range = get_item_condition_ranges(item)[item_condition].max_value

        if (item_left_range <= conversion_range.min_value < item_right_range or
                item_left_range < conversion_range.max_value <= item_right_range):
            res[item_cond] = conversion_range.max_value

    return res
