import os

import yaml
from typing import NamedTuple, Set, Dict

INVENTORY_PATH = os.path.join('epics', 'data', 'inventory.yaml')


class InventoryItem(NamedTuple):
    template_id: int
    entity_type: str
    mint: str
    score: float

    @property
    def key(self) -> str:
        return f'{self.entity_type}-{self.template_id}'


def save_inventory(inv: Set[InventoryItem], file_path: str = INVENTORY_PATH):
    with open(file_path, 'w') as f:
        yaml.dump({i.key: {'k': i.mint, 's': i.score} for i in inv}, f, default_flow_style=False)


def load_inventory(file_path: str = INVENTORY_PATH) -> Dict[int, InventoryItem]:
    with open(file_path) as f:
        data = yaml.load(f, Loader=yaml.SafeLoader)
        return {
            key: InventoryItem(key.split('-')[1], key.split('-')[0], details['k'], details['s'])
            for key, details in data.items()
        }
