from typing import NamedTuple, Dict, Optional

from enum import IntEnum


class PriceTimeRange(IntEnum):
    HOURS_24 = 0
    DAYS_7 = 1
    DAYS_30 = 2
    DAYS_90 = 3
    DAYS_365 = 4
    ALL_TIME = 5


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


LFPrices = Dict[str, LFItemPrice]
