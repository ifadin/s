from typing import NamedTuple, List, Dict

from csgo.conversion import FloatRange
from csgo.type.item import Item, ItemCondition
from csgo.type.price import ItemWithPrice

OutputItems = Dict[str, float]


class ContractReturn(NamedTuple):
    @property
    def contract_roi(self) -> float:
        return self.contract_revenue / self.contract_investment

    @property
    def contract_revenue(self) -> float:
        return self.contract_return - self.contract_investment

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
