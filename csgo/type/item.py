from typing import NamedTuple, List, Tuple

from enum import IntEnum


class Item(NamedTuple):
    name: str
    rarity: int
    collection_name: str
    min_float: float = 0
    max_float: float = 1
    st_track: bool = False

    @property
    def full_name(self) -> str:
        st_track = 'StatTrak™ ' if self.st_track else ''
        return f'{st_track}{self.name}'


def to_st_track(item: Item) -> Item:
    return Item(item.name, item.rarity, item.collection_name, item.min_float, item.max_float, st_track=True)


def to_basic(item: Item) -> Item:
    return Item(item.name, item.rarity, item.collection_name, item.min_float, item.max_float, st_track=False)


class ItemCollection(NamedTuple):
    name: str
    items: List[Item]
    st_track: bool = None


class ItemCondition(IntEnum):
    BATTLE_SCARED = 0
    WELL_WORN = 1
    FIELD_TESTED = 2
    MINIMAL_WEAR = 3
    FACTORY_NEW = 4

    def __str__(self) -> str:
        names = {
            self.BATTLE_SCARED: 'Battle-Scarred',
            self.WELL_WORN: 'Well-Worn',
            self.FIELD_TESTED: 'Field-Tested',
            self.MINIMAL_WEAR: 'Minimal Wear',
            self.FACTORY_NEW: 'Factory New'
        }
        return names[self]

    @classmethod
    def from_short_str(cls, value: str):
        if value is None:
            return None

        names = {
            'bs': cls.BATTLE_SCARED,
            'ww': cls.WELL_WORN,
            'ft': cls.FIELD_TESTED,
            'mw': cls.MINIMAL_WEAR,
            'fn': cls.FACTORY_NEW
        }
        return names.get(value.lower())

    @classmethod
    def to_short_str(cls, value) -> str:
        names = {
            cls.BATTLE_SCARED: 'BS',
            cls.WELL_WORN: 'WW',
            cls.FIELD_TESTED: 'FT',
            cls.MINIMAL_WEAR: 'MW',
            cls.FACTORY_NEW: 'FN'
        }
        return names[value]


class ItemRarity(IntEnum):
    CONSUMER_GRADE = 0
    INDUSTRIAL_GRADE = 1
    MIL_SPEC_GRADE = 2
    RESTRICTED = 3
    CLASSIFIED = 4
    COVERT = 5
    EXTRAORDINARY = 6
    CONTRABAND = 7

    @classmethod
    def from_short_str(cls, value: str):
        if value is None:
            return None

        names = {
            'wc': cls.CONSUMER_GRADE,
            'wu': cls.INDUSTRIAL_GRADE,
            'wr': cls.MIL_SPEC_GRADE,
            'wm': cls.RESTRICTED,
            'wa': cls.COVERT
        }
        return names.get(value.lower())


ItemWithCondition = Tuple[Item, ItemCondition]
