from typing import List, Dict, Optional

import yaml

from csgo.type.item import Item, ItemCollection


def get_next_level_items(item: Item, collection: ItemCollection) -> List[Item]:
    if item.collection_name != collection.name:
        raise AssertionError(f'Item {item.name} is from another collection')
    return [Item(c_item.name, c_item.rarity, c_item.collection_name, c_item.min_float, c_item.max_float, item.st_track)
            for c_item in collection.items if c_item.rarity - item.rarity == 1]


def get_prev_level_items(item: Item, collection: ItemCollection) -> List[Item]:
    if item.collection_name != collection.name:
        raise AssertionError(f'Item {item.name} is from another collection')
    return [Item(c_item.name, c_item.rarity, c_item.collection_name, c_item.min_float, c_item.max_float, item.st_track)
            for c_item in collection.items if item.rarity - c_item.rarity == 1]


def load_collections() -> Dict[str, ItemCollection]:
    with open('csgo/collections.yaml') as f:
        res = yaml.load(f, Loader=yaml.SafeLoader)
        return {
            col_name: ItemCollection(col_name, [
                Item(item_name, item_details['rarity'], col_name, item_details['min_float'], item_details['max_float'])
                for item_name, item_details
                in col_details['items'].items()], col_details['st_track'])
            for col_name, col_details
            in res['collections'].items()
        }


def get_item_from_collection(item_name: str, collections: Dict[str, ItemCollection]) -> Optional[Item]:
    return next((i for collection in collections.values() for i in collection.items if i.name == item_name), None)
