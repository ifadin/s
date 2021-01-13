import os

import yaml
from typing import NamedTuple, Set, Dict

INVENTORY_PATH = os.path.join('epics', 'data', 'inventory.yaml')


class InventoryItem(NamedTuple):
    template_id: int
    key: str
    updated_at: int


def save_inventory(inv: Set[InventoryItem], file_path: str = INVENTORY_PATH):
    with open(file_path, 'w') as f:
        yaml.dump({i.template_id: {'k': i.key, 'u': i.updated_at} for i in inv}, f, default_flow_style=False)


def load_inventory(file_path: str = INVENTORY_PATH) -> Dict[int, InventoryItem]:
    with open(file_path) as f:
        data = yaml.load(f, Loader=yaml.SafeLoader)
        return {
            template_id: InventoryItem(template_id, details['k'], details.get('u'))
            for template_id, details in data.items()
        }
