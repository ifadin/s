from typing import NamedTuple, List, Dict

from csgo.type.float import FloatRange, get_item_condition_from_float
from csgo.type.item import Item, ItemCondition
from csgo.type.price import ItemWithPrice

OutputItems = Dict[str, float]


class ContractItem(NamedTuple):
    item: Item
    item_price: float
    item_float: float

    @property
    def item_condition(self) -> ItemCondition:
        return get_item_condition_from_float(self.item_float)

    @property
    def market_name(self):
        return self.item.full_name + f' ({str(self.item_condition)})'


class ContractReturn(NamedTuple):
    @property
    def contract_roi(self) -> float:
        return self.contract_revenue / self.contract_investment

    @property
    def contract_revenue(self) -> float:
        return self.contract_return - self.contract_investment

    source_items: List[ContractItem]
    outcome_items: List[ItemWithPrice]
    contract_investment: float
    contract_return: float
    avg_float: float
    approximated: bool = False
    guaranteed: bool = False
    warnings: List[str] = None


class ItemReturn(NamedTuple):
    item: Item
    item_condition: ItemCondition
    item_investment: float
    item_return: float
    float_range: FloatRange
    item_float: float = None
    guaranteed: bool = False
    output_items: OutputItems = None

    @property
    def item_revenue(self) -> float:
        return self.item_return - self.item_investment

    @property
    def item_roi(self) -> float:
        return self.item_revenue / self.item_investment
