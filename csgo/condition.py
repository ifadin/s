from typing import NamedTuple, Dict, List

from csgo.type.item import ItemCondition, Item

eps = 0.000000000001


class FloatRange(NamedTuple):
    min_value: float
    max_value: float

    def __contains__(self, value: float) -> bool:
        return self.min_value < value < self.max_value

    def __str__(self) -> str:
        return f'[{self.min_value}, {self.max_value}]'


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


def get_item_conversion_ranges(item: Item) -> Dict[ItemCondition, FloatRange]:
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


def get_item_possible_conversions(item: Item,
                                  item_condition: ItemCondition,
                                  target_item: Item) -> Dict[ItemCondition, FloatRange]:
    res = {}
    item_range_left = get_item_condition_ranges(item)[item_condition].min_value
    item_range_right = get_item_condition_ranges(item)[item_condition].max_value
    item_float_range = FloatRange(item_range_left, item_range_right)

    for conv_cond, conversion_range in get_item_conversion_ranges(target_item).items():
        if (item_range_right - eps in conversion_range or
                item_range_left + eps in conversion_range or
                conversion_range.min_value in item_float_range or
                conversion_range.max_value in item_float_range):
            res[conv_cond] = FloatRange(max((item_range_left, conversion_range.min_value)),
                                        min((item_range_right, conversion_range.max_value)))

    return res
