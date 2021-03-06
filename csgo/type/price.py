from typing import NamedTuple, Dict, Optional, Union, List

from enum import IntEnum

from csgo.type.item import Item, ItemCondition, ItemRarity, ST_PREFIX


class PriceTimeRange(IntEnum):
    HOURS_24 = 0
    DAYS_7 = 1
    DAYS_30 = 2
    DAYS_90 = 3
    DAYS_365 = 4
    ALL_TIME = 5


class PriceEntry(NamedTuple):
    market_hash_name: str
    price: float
    float_value: float
    item_rarity: Union[str, ItemRarity] = None
    item_name: str = None
    withdrawable_in: int = None
    item_id: str = None
    in_market: bool = None

    @property
    def st_track(self) -> bool:
        return self.market_hash_name.startswith(ST_PREFIX)


class SaleEntry(NamedTuple):
    item_name: str
    price: float
    updated_at: int


class PriceDetails(NamedTuple):
    prices: List[PriceEntry]
    updated_at: int


ItemPrices = Dict[str, PriceDetails]
ItemSales = Dict[str, SaleEntry]
BSSalesHistory = Dict[str, List[float]]


class ItemWithPrice(NamedTuple):
    item: Item
    item_price: float
    item_condition: ItemCondition

    @property
    def market_name(self):
        return self.item.full_name + f' ({str(self.item_condition)})'


class STItemPriceDetails(NamedTuple):
    average: float
    sold: int
    median: float = None
    standard_deviation: float = None
    lowest_price: float = None
    highest_price: float = None


class STItemPrice(NamedTuple):
    item_name: str
    prices: Dict[PriceTimeRange, STItemPriceDetails]


STPrices = Dict[str, STItemPrice]


class LFItemPrice(NamedTuple):
    name: str
    price: float
    have: int
    max: int
    rate: float
    tradable: int
    reservable: int


LFSales = Dict[str, LFItemPrice]


def get_market_name(item_name: Union[str, Item], item_condition: ItemCondition) -> str:
    item_name = item_name.full_name if isinstance(item_name, Item) else item_name
    return f'{item_name} ({str(item_condition)})'


def get_price_time_range_from_bck_string(value: str) -> Optional[PriceTimeRange]:
    names = {
        '24_hours': PriceTimeRange.HOURS_24,
        '7_days': PriceTimeRange.DAYS_7,
        '30_days': PriceTimeRange.DAYS_30,
        'all_time': PriceTimeRange.ALL_TIME
    }
    return names.get(value)


def get_price_time_range_from_hexa_string(value: str) -> Optional[PriceTimeRange]:
    names = {
        '1': PriceTimeRange.HOURS_24,
        '7': PriceTimeRange.DAYS_7,
        '30': PriceTimeRange.DAYS_30,
        '90': PriceTimeRange.DAYS_90,
        '365': PriceTimeRange.DAYS_365
    }
    return names.get(value)
