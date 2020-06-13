from typing import NamedTuple, List, Dict

from csgo.type.float import FloatRange
from csgo.type.item import Item, ItemCondition
from csgo.type.price import ItemWithPrice, PriceEntry

OutputItems = Dict[str, float]


class ContractItem(NamedTuple):
    item: Item
    price_entry: PriceEntry


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
    warnings: List[str] = None

    @property
    def guaranteed(self) -> bool:
        if len(set(self.outcome_items)) == 1:
            return True
        return False


class ItemReturn(NamedTuple):
    item: Item
    item_condition: ItemCondition
    item_investment: float
    item_return: float
    float_range: FloatRange
    item_float: float = None
    output_items: OutputItems = None
    item_id: str = None

    @property
    def item_revenue(self) -> float:
        return self.item_return - self.item_investment

    @property
    def item_roi(self) -> float:
        return self.item_revenue / self.item_investment

    @property
    def guaranteed(self) -> bool:
        if len(self.output_items) == 1:
            return True
        return False
