from typing import NamedTuple, List

from enum import IntEnum


class Item(NamedTuple):
    name: str
    rarity: int
    collection_name: str


class ItemCollection(NamedTuple):
    name: str
    items: List[Item]


class ItemCondition(IntEnum):
    BATTLE_SCARED = 0
    WELL_WORN = 1
    FIELD_TESTED = 2
    MINIMAL_WEAR = 3
    FACTORY_NEW = 4

    def __str__(self):
        names = {
            self.BATTLE_SCARED: 'Battle-Scarred',
            self.WELL_WORN: 'Well-Worn',
            self.FIELD_TESTED: 'Field-Tested',
            self.MINIMAL_WEAR: 'Minimal Wear',
            self.FACTORY_NEW: 'Factory New'
        }
        return names[self]


class ItemRarity(IntEnum):
    CONSUMER_GRADE = 0
    INDUSTRIAL_GRADE = 1
    MIL_SPEC_GRADE = 2
    RESTRICTED = 3
    CLASSIFIED = 4
    COVERT = 5
    EXTRAORDINARY = 6
    CONTRABAND = 7
