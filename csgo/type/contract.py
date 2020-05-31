from typing import NamedTuple, List

from csgo.type.item import Item, ItemCondition


class ContractReturn(NamedTuple):
    @property
    def contract_roi(self) -> float:
        return self.contract_revenue / self.contract_investment

    @property
    def contract_revenue(self) -> float:
        return self.contract_return - self.contract_investment

    items: List[Item]
    item_condition: ItemCondition
    contract_investment: float
    contract_return: float
    approximated: bool = False
    guaranteed: bool = False
