import os
from typing import Optional, NamedTuple

import requests

from csgo.type.item import ItemCondition


def get_float_value(a: str, d: str) -> Optional[float]:
    user_id = os.environ.get('ST_USER_ID')
    if not user_id:
        raise AssertionError('ST user id is required')

    res = requests.get(f'https://api.csgofloat.com/?url='
                       f'steam://rungame/730/76561202255233023/+csgo_econ_action_preview%20'
                       f'S{user_id}A{a}{d}')
    res.raise_for_status()
    return res.json().get('iteminfo', {}).get('floatvalue')


class FloatRange(NamedTuple):
    min_value: float
    max_value: float

    @property
    def item_condition(self) -> ItemCondition:
        return next((c for c in ItemCondition if is_in_float_range(self, ItemConditionRanges[c])))

    def __contains__(self, value: float) -> bool:
        return self.min_value < value < self.max_value

    def __str__(self) -> str:
        return f'[{self.min_value}, {self.max_value}]'


def is_in_float_range(src_float_range: FloatRange, target_float_range: FloatRange) -> bool:
    return target_float_range.min_value <= src_float_range.min_value and src_float_range.max_value <= target_float_range.max_value


ItemConditionRanges = {
    ItemCondition.BATTLE_SCARED: FloatRange(0.45, 1),
    ItemCondition.WELL_WORN: FloatRange(0.38, 0.45),
    ItemCondition.FIELD_TESTED: FloatRange(0.15, 0.38),
    ItemCondition.MINIMAL_WEAR: FloatRange(0.07, 0.15),
    ItemCondition.FACTORY_NEW: FloatRange(0, 0.07)
}


def get_item_condition_from_float(float_value: float) -> ItemCondition:
    for cond in ItemCondition:
        cond_range = ItemConditionRanges[cond]
        if cond_range.min_value <= float_value:
            if (float_value <= cond_range.max_value
            if cond == ItemCondition.BATTLE_SCARED
            else float_value < cond_range.max_value):
                return cond
