from typing import List

from csgo.type.item import Item, ItemCollection


def get_next_level_items(item: Item, collection: ItemCollection) -> List[Item]:
    if item.collection_name != collection.name:
        raise AssertionError(f'Item {item.name} is from another collection')
    return [c_item for c_item in collection.items if c_item.rarity - item.rarity == 1]


def get_prev_level_items(item: Item, collection: ItemCollection) -> List[Item]:
    if item.collection_name != collection.name:
        raise AssertionError(f'Item {item.name} is from another collection')
    return [c_item for c_item in collection.items if item.rarity - c_item.rarity == 1]
